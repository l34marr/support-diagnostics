#!/usr/bin/env python3
"""
check_tls.py – TLS / Security Health Check
Analyses TLS certificate and security configuration from the
elastic/support-diagnostics bundle.
"""

import re
import sys
from datetime import datetime, timezone
from utils import DiagnosticBundle, section, row, warn, fail, ok, info, BOLD, RESET


# Thresholds
CERT_EXPIRY_WARN_DAYS = 90
CERT_EXPIRY_FAIL_DAYS = 30
WEAK_CIPHERS = {
    "RC4", "3DES", "DES", "EXPORT", "NULL", "ANON", "MD5",
    "TLS_RSA_WITH_AES_128_CBC_SHA",   # no forward secrecy
    "TLS_RSA_WITH_AES_256_CBC_SHA",
}
PREFERRED_TLS_VERSIONS = {"TLSv1.3", "TLSv1.2"}
DEPRECATED_TLS_VERSIONS = {"TLSv1", "TLSv1.0", "TLSv1.1", "SSLv2", "SSLv3"}


def _parse_iso_date(s: str) -> datetime | None:
    """Parse ISO-8601 date string to datetime."""
    if not s:
        return None
    s = s.strip().rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%b %d %H:%M:%S %Y GMT", "%Y%m%d%H%M%SZ"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _days_until(dt: datetime) -> int:
    now = datetime.now(tz=timezone.utc)
    return (dt - now).days


def check_tls_certificates(b: DiagnosticBundle) -> int:
    issues = 0
    section("TLS CERTIFICATES")

    # Support-diagnostics may include: ssl_certs.json, nodes_info.json (ssl section)
    certs_json = b.read_json("ssl_certs.json")
    if certs_json is None:
        certs_json = b.read_json("certificates.json")

    if certs_json is None:
        info("ssl_certs.json / certificates.json not found – checking nodes_info.json")
        certs_json = _extract_certs_from_nodes_info(b)

    if not certs_json:
        warn("No TLS certificate data found in bundle")
        warn("Ensure X-Pack security is enabled and diagnostic was run with credentials")
        return 0

    # Normalise: support both list and {nodes: {node: {certificates: [...]}}} formats
    cert_list = _normalise_cert_list(certs_json)
    row("Certificates found", str(len(cert_list)), "info")

    now = datetime.now(tz=timezone.utc)
    seen_subjects: set[str] = set()

    for cert in cert_list:
        subject   = cert.get("subject", {})
        not_after = cert.get("expiry") or cert.get("not_after") or cert.get("valid_until", "")
        san       = cert.get("san", {})
        path      = cert.get("path", "")
        issuer    = cert.get("issuer", {})

        subj_str = (
            subject.get("CN") or
            subject.get("common_name") or
            str(subject)
        )[:80]

        if subj_str in seen_subjects:
            continue
        seen_subjects.add(subj_str)

        print(f"\n  {BOLD}{subj_str}{RESET}")
        if path:
            print(f"    Path   : {path}")

        # Expiry
        exp_dt = _parse_iso_date(str(not_after))
        if exp_dt:
            days = _days_until(exp_dt)
            exp_level = ("ok"   if days > CERT_EXPIRY_WARN_DAYS else
                         "warn" if days > CERT_EXPIRY_FAIL_DAYS else "fail")
            row("    Expires", f"{exp_dt.strftime('%Y-%m-%d')}  ({days} days)", exp_level)
            if days <= CERT_EXPIRY_FAIL_DAYS:
                fail(f"    Certificate expires in {days} days – URGENT renewal required")
                issues += 1
            elif days <= CERT_EXPIRY_WARN_DAYS:
                warn(f"    Certificate expires in {days} days – plan renewal")
        else:
            row("    Expires", str(not_after) or "n/a", "info")

        # Self-signed check
        issuer_cn  = (issuer.get("CN") or issuer.get("common_name", "")) if isinstance(issuer, dict) else str(issuer)
        self_signed = issuer_cn and issuer_cn == subj_str
        row("    Self-signed", str(self_signed), "warn" if self_signed else "ok")
        if self_signed:
            warn("    Self-signed certificate – acceptable for transport, not recommended for HTTP layer")

        # SANs
        dns_names = san.get("dns", []) if isinstance(san, dict) else []
        ip_addrs  = san.get("ip", [])  if isinstance(san, dict) else []
        if dns_names or ip_addrs:
            info(f"    SANs: {', '.join(dns_names + ip_addrs)}")

    return issues


def _normalise_cert_list(data) -> list:
    """Convert various certificate JSON shapes to a flat list."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # {nodes: {node_id: {certificates: [...]}}}
        certs = []
        for v in data.values():
            if isinstance(v, dict):
                inner = v.get("certificates") or v.get("certs", [])
                if isinstance(inner, list):
                    certs.extend(inner)
                else:
                    certs.append(v)
            elif isinstance(v, list):
                certs.extend(v)
        return certs
    return []


def _extract_certs_from_nodes_info(b: DiagnosticBundle) -> list:
    """Try to extract SSL cert paths from nodes_info.json settings."""
    ni = b.read_json("nodes_info.json")
    if not ni:
        return []
    certs = []
    for node_id, node in ni.get("nodes", {}).items():
        ssl = node.get("settings", {}).get("xpack", {}).get("security", {}).get("transport", {}).get("ssl", {})
        if ssl:
            cert_path  = ssl.get("certificate") or ssl.get("keystore.path", "")
            if cert_path:
                certs.append({"subject": {"CN": cert_path}, "path": cert_path})
    return certs


def check_security_settings(b: DiagnosticBundle) -> int:
    issues = 0
    section("SECURITY SETTINGS")

    nodes_info = b.read_json("nodes_info.json")
    if nodes_info is None:
        info("nodes_info.json not found – skipping security settings check")
        return 0

    security_flags: dict[str, set] = {}

    for node_id, ni in nodes_info.get("nodes", {}).items():
        name     = ni.get("name", node_id)
        settings = ni.get("settings", {})
        xpack    = settings.get("xpack", {})
        security = xpack.get("security", {})

        enabled = str(security.get("enabled", "")).lower()
        http_ssl = str(
            security.get("http",      {}).get("ssl", {}).get("enabled", "") or
            settings.get("http",      {}).get("ssl", {}).get("enabled", "")
        ).lower()
        transport_ssl = str(
            security.get("transport", {}).get("ssl", {}).get("enabled", "") or
            settings.get("transport", {}).get("ssl", {}).get("enabled", "")
        ).lower()

        security_flags.setdefault("security_enabled", set()).add(enabled or "unknown")
        security_flags.setdefault("http_ssl",         set()).add(http_ssl or "unknown")
        security_flags.setdefault("transport_ssl",    set()).add(transport_ssl or "unknown")

    def _majority(vals: set) -> str:
        return next(iter(vals), "unknown")

    sec_en = _majority(security_flags.get("security_enabled", {"unknown"}))
    http_s = _majority(security_flags.get("http_ssl",         {"unknown"}))
    tra_s  = _majority(security_flags.get("transport_ssl",    {"unknown"}))

    row("X-Pack security enabled",  sec_en or "unknown",
        "ok" if sec_en == "true" else "fail")
    if sec_en == "false":
        fail("Security is disabled – cluster data is unauthenticated and unencrypted")
        issues += 1

    row("HTTP  layer TLS",       http_s or "unknown",
        "ok" if http_s == "true" else "warn")
    row("Transport layer TLS",   tra_s  or "unknown",
        "ok" if tra_s  == "true" else "fail")

    if tra_s == "false":
        fail("Transport TLS is disabled – inter-node communication is unencrypted")
        issues += 1
    if http_s == "false":
        warn("HTTP TLS is disabled – client communication is unencrypted")
        issues += 1

    return issues


def check_tls_protocols(b: DiagnosticBundle) -> int:
    issues = 0
    section("TLS PROTOCOLS & CIPHERS")

    # Check for protocol / cipher configuration in cluster settings or node settings
    cs = b.read_json("cluster_settings.json")
    ni = b.read_json("nodes_info.json")

    all_settings: dict = {}

    if cs:
        for layer in ("persistent", "transient"):
            for k, v in cs.get(layer, {}).items():
                all_settings[k] = v

    if ni:
        for nid, node in ni.get("nodes", {}).items():
            def _flatten(d, prefix=""):
                for k, v in d.items():
                    full = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, dict):
                        _flatten(v, full)
                    else:
                        all_settings[full] = v
            _flatten(node.get("settings", {}))
        break_outer = False

    # Look for ssl.protocols / ssl.cipher_suites keys
    proto_keys  = [k for k in all_settings if "ssl.supported_protocols" in k or "ssl.protocols" in k]
    cipher_keys = [k for k in all_settings if "cipher_suites" in k or "ciphers" in k]

    if not proto_keys and not cipher_keys:
        info("No explicit TLS protocol/cipher configuration found – Elasticsearch defaults apply")
        info("Default: TLSv1.2 + TLSv1.3 (ES 8.x); TLSv1.2 (ES 7.x)")
        return 0

    for k in proto_keys:
        val = str(all_settings[k])
        protocols = [p.strip() for p in val.strip("[]").split(",")]
        deprecated = [p for p in protocols if p in DEPRECATED_TLS_VERSIONS]
        row(f"Protocols ({k.split('.')[-3]})", ", ".join(protocols),
            "ok" if not deprecated else "warn")
        if deprecated:
            warn(f"Deprecated TLS protocol(s) configured: {', '.join(deprecated)}")
            issues += 1

    for k in cipher_keys:
        val = str(all_settings[k])
        ciphers = [c.strip() for c in val.strip("[]").split(",")]
        weak = [c for c in ciphers if any(w in c for w in WEAK_CIPHERS)]
        row(f"Ciphers ({k.split('.')[-3]})", f"{len(ciphers)} configured",
            "ok" if not weak else "warn")
        if weak:
            warn(f"Weak cipher(s) in use: {', '.join(weak)}")
            issues += 1

    return issues


def main(zip_path: str) -> None:
    b = DiagnosticBundle(zip_path)
    total = 0
    total += check_security_settings(b)
    total += check_tls_certificates(b)
    total += check_tls_protocols(b)

    section("TLS / SECURITY SUMMARY")
    if total == 0:
        ok("No TLS / security issues detected")
    else:
        fail(f"{total} TLS / security issue(s) found – review warnings above")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-diagnostics.zip>")
        sys.exit(1)
    main(sys.argv[1])
