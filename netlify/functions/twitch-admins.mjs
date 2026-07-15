const TWITCH_USER_IDS = ["74202440", "20092299", "29233312"];

let appToken = "";
let appTokenExpiresAt = 0;

async function getAppToken(clientId, clientSecret, forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && appToken && now < appTokenExpiresAt) {
    return appToken;
  }

  const body = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: "client_credentials",
  });
  const response = await fetch("https://id.twitch.tv/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    throw new Error(`Twitch token request failed: ${response.status}`);
  }

  const payload = await response.json();
  appToken = payload.access_token;
  appTokenExpiresAt = now + Math.max(60, Number(payload.expires_in || 0) - 300) * 1000;
  return appToken;
}

async function fetchUsers(clientId, clientSecret, forceRefresh = false) {
  const token = await getAppToken(clientId, clientSecret, forceRefresh);
  const query = new URLSearchParams();
  TWITCH_USER_IDS.forEach(id => query.append("id", id));
  const response = await fetch(`https://api.twitch.tv/helix/users?${query}`, {
    headers: {
      "Client-Id": clientId,
      "Authorization": `Bearer ${token}`,
    },
  });

  if (response.status === 401 && !forceRefresh) {
    return fetchUsers(clientId, clientSecret, true);
  }
  if (!response.ok) {
    throw new Error(`Twitch users request failed: ${response.status}`);
  }
  return response.json();
}

export const handler = async () => {
  const clientId = process.env.TWITCH_CLIENT_ID;
  const clientSecret = process.env.TWITCH_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    return {
      statusCode: 503,
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ error: "Twitch API is not configured" }),
    };
  }

  try {
    const payload = await fetchUsers(clientId, clientSecret);
    const users = (payload.data || []).map(user => ({
      id: user.id,
      login: user.login,
      displayName: user.display_name,
    }));
    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "public, max-age=60, s-maxage=300, stale-while-revalidate=3600",
      },
      body: JSON.stringify({ users }),
    };
  } catch (error) {
    console.error("Unable to refresh Twitch administrators:", error.message);
    return {
      statusCode: 502,
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ error: "Unable to load Twitch users" }),
    };
  }
};
