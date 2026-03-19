import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/", "/login", "/register"];
const PUBLIC_PATH_PREFIXES = ["/api/", "/_next/", "/favicon", "/health"];
const AUTH_TOKEN_KEY = "novel_agent_token";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublicPath =
    PUBLIC_PATHS.includes(pathname) ||
    PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (isPublicPath) {
    return NextResponse.next();
  }

  const token =
    request.cookies.get(AUTH_TOKEN_KEY)?.value ||
    request.headers.get("authorization")?.replace("Bearer ", "");

  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
