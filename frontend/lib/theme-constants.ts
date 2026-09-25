// 不加 "use client"：root layout（Server Component）要讀到實際字串，而不是 client reference。

export type Theme = "dark" | "light";

// 與 globals.css 的 --background 同值；網址列／狀態列顏色跟著主題走
export const THEME_BACKGROUND: Record<Theme, string> = { dark: "#0d1520", light: "#f3f6f9" };

/** 首次繪製前套用主題（layout 內嵌），避免深淺閃爍；沒選過就用深色 */
export const THEME_BOOT_SCRIPT = `(function(){var t="dark";try{if(localStorage.getItem("theme")==="light")t="light"}catch(e){}document.documentElement.setAttribute("data-theme",t)})();`;
