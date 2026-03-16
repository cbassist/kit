#!/bin/bash
# Ping Supabase projects to prevent auto-pause on free tier.
# Run via cron on VPS: */6 * * * * /path/to/keepalive.sh >> /var/log/supabase-keepalive.log 2>&1

# 01 Lab database
curl -sf "https://zmdawyhpolrkjwihqury.supabase.co/rest/v1/goals?select=count&limit=1" \
  -H "apikey: ${SUPABASE_01_ANON_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_01_ANON_KEY}" \
  -o /dev/null && echo "$(date) | 01-lab: alive" || echo "$(date) | 01-lab: DOWN"

# Archon database
curl -sf "https://urfcubpjsvzikpybxucb.supabase.co/rest/v1/?limit=1" \
  -H "apikey: ${SUPABASE_ARCHON_ANON_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_ARCHON_ANON_KEY}" \
  -o /dev/null && echo "$(date) | archon: alive" || echo "$(date) | archon: DOWN"
