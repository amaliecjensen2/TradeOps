import type { Config } from "tailwindcss";

const config: Config = {
    content: ["./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                up: "#22c55e",
                down: "#ef4444",
                warn: "#f59e0b",
            },
        },
    },
    plugins: [],
};

export default config;
