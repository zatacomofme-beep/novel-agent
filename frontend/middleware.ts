import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/", "/login", "/register"];
const PUBLIC_PATH_PREFIXES = ["/api/", "/_next/", "/favicon", "/health", "/@vite"];
const AUTH_TOKEN_KEY = "novel_agent_token";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token
      .split(".")[1]
      ?.replace(/-/g, "+")
      .replace(/_/g, "/");
    if (!base64) {
      return null;
    }
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") {
    return true;
  }
  return Date.now() >= payload.exp * 1000;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublicPath =
    PUBLIC_PATHS.includes(pathname) ||
    PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (isPublicPath) {
    return NextResponse.next();
  }

  const cookieToken = request.cookies.get(AUTH_TOKEN_KEY)?.value ?? null;
  const headerToken =
    request.headers.get("authorization")?.replace("Bearer ", "") ?? null;
  const token =
    (cookieToken && !isTokenExpired(cookieToken) ? cookieToken : null) ||
    (headerToken && !isTokenExpired(headerToken) ? headerToken : null);

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    if (cookieToken) {
      response.cookies.set(AUTH_TOKEN_KEY, "", {
        maxAge: 0,
        path: "/",
      });
    }
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|@vite|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
