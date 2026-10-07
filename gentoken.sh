cd /home/guto/Desktop/mypy/agente_macro_poc
touch .env
TOKEN="$(openssl rand -hex 32)"
if grep -q '^APP_TOKEN=' .env; then
  sed -i "s/^APP_TOKEN=.*/APP_TOKEN=$TOKEN/" .env
else
  printf '\nAPP_TOKEN=%s\n' "$TOKEN" >> .env
fi
printf 'Cole este token na página: %s\n' "$TOKEN"