// OAuth login URL construction (pure, no browser globals required).
//
// The provider round-trip always runs through the API backend; the `next`
// query parameter tells the backend which frontend origin started the flow
// so its post-auth redirect returns there (localhost dev server vs the
// production deployment). The backend only honors allow-listed origins.
export function oauthLoginUrl(apiBaseUrl, provider, frontendOrigin) {
  const normalizedBase = String(apiBaseUrl || "").replace(/\/+$/, "");
  const params = new URLSearchParams();
  if (frontendOrigin) {
    params.set("next", frontendOrigin);
  }
  const query = params.toString();
  return `${normalizedBase}/auth/${provider}${query ? `?${query}` : ""}`;
}
