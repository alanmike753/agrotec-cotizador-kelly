import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Cotizador Kelly · Agrotec de Occidente",
    short_name: "Kelly Agrotec",
    description: "Cotizador comercial privado de implementos Kelly",
    start_url: "/",
    display: "standalone",
    background_color: "#f4f3ed",
    theme_color: "#123b2b",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" }],
  };
}
