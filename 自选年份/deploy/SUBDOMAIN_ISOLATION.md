# 15min Subdomain Isolation

Goal: deploy the 15min site without affecting `globalreviewops.xyz`.

Use only the subdomain host:

- `15min.globalreviewops.xyz`

Do not replace or edit the existing parent site block for:

- `globalreviewops.xyz`
- `www.globalreviewops.xyz`

Runtime isolation:

- Static files: `C:\www\15min\static`
- API files: `C:\www\15min\api`
- Logs: `C:\www\15min\logs`
- API port: `127.0.0.1:8765`

For the current Windows server that uses Caddy, append only the contents of:

- `deploy\Caddyfile.15min-subdomain`

Then validate and reload Caddy:

```powershell
C:\globalreviewops\caddy\caddy.exe validate --config C:\globalreviewops\Caddyfile --adapter caddyfile
Get-Process caddy -ErrorAction SilentlyContinue | Stop-Process -Force
schtasks /Run /TN GlobalReviewOpsCaddy
```

Acceptance checks:

```powershell
curl.exe -I https://globalreviewops.xyz/
curl.exe -I https://15min.globalreviewops.xyz/
curl.exe https://15min.globalreviewops.xyz/api/stats
```

The parent site must still return the existing review collection console. The subdomain must return the 15min city viewer.
