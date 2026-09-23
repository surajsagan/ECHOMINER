proxy_http_version 1.1;
proxy_set_header Host $host;
# $remote_addr is the real visitor IP (restored from CF-Connecting-IP, trusted
# only when the connection comes from a Cloudflare range). The client-supplied
# headers are overwritten so they cannot be spoofed.
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header CF-Connecting-IP $remote_addr;
proxy_set_header X-Forwarded-Proto https;
