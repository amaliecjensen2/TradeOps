import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Context = {
    params: {
        path: string[];
    };
};

export async function GET(request: NextRequest, context: Context) {
    const path = context.params.path.join("/");
    const upstream = new URL(`/${path}`, API_URL);
    upstream.search = request.nextUrl.search;

    const response = await fetch(upstream, { cache: "no-store" });
    const body = await response.text();

    return new NextResponse(body, {
        status: response.status,
        headers: {
            "content-type": response.headers.get("content-type") ?? "application/json",
        },
    });
}
