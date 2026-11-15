import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const firebaseConfig = {
  apiKey: "AIzaSyC10TN1pzrwAfGyLMH7vNRIPObW58YzcNI",
  authDomain: "ucc-immunoclinic.firebaseapp.com",
  projectId: "ucc-immunoclinic",
  storageBucket: "ucc-immunoclinic.firebasestorage.app",
  messagingSenderId: "70400191615",
  appId: "1:70400191615:web:1ad1a784a163ee979f634a",
  measurementId: "G-EK3KEKK7R5",
};

const noStore = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };

export async function GET(request: Request) {
  const url = new URL(request.url);
  if (url.searchParams.get("format") === "worker") {
    const script = `self.__IMMUNO_FIREBASE_CONFIG__ = ${JSON.stringify(firebaseConfig)};`;
    return new Response(script, {
      headers: { ...noStore, "Content-Type": "application/javascript; charset=utf-8" },
    });
  }

  const vapidKey = process.env.FIREBASE_WEB_VAPID_KEY?.trim();
  if (!vapidKey) {
    return NextResponse.json(
      { message: "Las notificaciones web no están configuradas." },
      { status: 503, headers: noStore },
    );
  }

  return NextResponse.json({ firebaseConfig, vapidKey }, { headers: noStore });
}
