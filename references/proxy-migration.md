# Proxy Change Checklist

When `PT_PROXY` is updated in `secrets.env`, the following must also be updated:

## 1. secrets.env
```
PT_PROXY=http://<NEW_IP>:7890
```

## 2. Memory (agent behavior)
Update the proxy address in the "代理规则（致命！）" memory entry via `memory(action='replace')`.

## 3. javbus-api Docker Compose
File: `~/javbus-api/docker-compose.yml`
```yaml
environment:
  - HTTP_PROXY=http://<NEW_IP>:7890
  - HTTPS_PROXY=http://<NEW_IP>:7890
```

## 4. Restart javbus-api container
```bash
docker compose -f ~/javbus-api/docker-compose.yml up -d
```

## 5. Verify
```bash
curl -s http://localhost:8922/api/movies/search?keyword=test | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'OK, {len(d[\"pagination\"][\"pages\"])} pages')"
```

## Notes
- user-preferences.md references `secrets.env` generically (`见 secrets.env → PT_PROXY`), so no update needed there.
- Template files (`templates/*`) use `<PT_PROXY>` placeholder, no update needed.
- The javbus-api container still runs with the OLD proxy until restarted — don't forget step 4.
