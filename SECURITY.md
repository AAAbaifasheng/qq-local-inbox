# Security Policy

## Supported version

Security fixes are applied to the latest `main` branch and the latest release. Older commits are not maintained.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Choose **Advisories** and **Report a vulnerability**.

Do not open a public issue containing API keys, NapCat tokens, chat logs, real screenshots, database files, or other personal data.

## Scope

Relevant areas include:

- local-only validation for NapCat WebSocket / HTTP endpoints
- loopback-only NapCat WebUI client, WebUI token storage, and QR login status handling
- onefile exe update download, SHA256 verification, backup, and rename-replace
- loopback-only Chaoxing bridge, token authentication, CORS origin checks, and request-size limits
- Windows DPAPI credential storage
- remote API consent and API key handling
- message text redaction, local SQLite storage, and data clearing
- JSON parsing and prompt-injection boundaries in the model classifier
- update manifest validation, download integrity, SHA256 verification, zip path checks, backup/rollback, and dev-checkout protection

## Data safety

Never attach any of the following to an issue, discussion, pull request, or screenshot:

- `secrets.dat`
- `settings.json`
- `inbox.sqlite3` or its WAL/SHM files
- real QQ chat logs or screenshots
- real 学习通 assignment pages, course links, or screenshots
- the generated `chaoxing_bridge.user.js` (it embeds the local bridge token)
- API keys, Access Tokens, bridge tokens, cookies, or account credentials

If a credential was exposed, rotate it at the provider and remove it from the local machine. Deleting a Git commit is not enough once a repository has been cloned or cached.

## Known limitations

- The SQLite database is not encrypted at the field level. Use Windows device encryption / BitLocker and protect the Windows account.
- Remote model mode sends message text and minimal context to the configured provider. Read the provider's privacy policy before enabling it.
- Classification and date inference can be wrong; every candidate requires human confirmation.
- NapCatQQ and QQ are third-party services. Use is subject to their terms, licenses, and local law.
- Clearing local data uses SQLite `secure_delete` / WAL checkpoint / `VACUUM`, but cannot guarantee removal from SSD wear-levelling, snapshots, or backups.
- The Chaoxing assignment reader is a best-effort userscript that parses page structure. 学习通 has no public student API; page changes can break extraction, and automated access may be subject to platform terms.
- Auto-update trusts the GitHub repository/release account and the SHA256 in the release manifest. It does not provide code signing or protection if the upstream account or release pipeline is compromised. Auto-apply is skipped in git checkouts by default.
- The NapCat WebUI token grants local management access to NapCat. It is stored with DPAPI, but any process running as the same Windows user may be able to invoke DPAPI decryption. Protect the Windows account.
- The QR login window displays a live login QR from NapCat. Do not screenshot or share it while valid; the user must complete the scan and phone confirmation.

## Dependencies

The only Python runtime dependency is `websocket-client` (Apache-2.0). Python, Tkinter, NapCatQQ, DeepSeek, Ollama, and LM Studio are external components. The optional Chaoxing bridge requires a third-party userscript manager (Tampermonkey or Violentmonkey); it is not bundled. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
