import { useCallback, useRef, useState } from "react";

const KEYS = {
  sidebarExpanded: "cognilance_sidebar_expanded",
  detailExpanded: "cognilance_detail_expanded",
  sidebarWidth: "cognilance_sidebar_width",
  detailWidth: "cognilance_detail_width",
} as const;

const DEFAULT_SIDEBAR_W = 288;
const DEFAULT_DETAIL_W = 384;
const MIN_SIDEBAR_W = 200;
const MAX_SIDEBAR_W = 480;
const MIN_DETAIL_W = 260;
const MAX_DETAIL_W = 560;

export { MIN_SIDEBAR_W, MAX_SIDEBAR_W, MIN_DETAIL_W, MAX_DETAIL_W };

function readBool(key: string, defaultValue: boolean) {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return defaultValue;
    return v === "true";
  } catch {
    return defaultValue;
  }
}

function readWidth(key: string, fallback: number) {
  try {
    const v = Number(localStorage.getItem(key));
    return Number.isFinite(v) && v > 0 ? v : fallback;
  } catch {
    return fallback;
  }
}

export function usePanelLayout() {
  const [sidebarExpanded, setSidebarExpanded] = useState(() =>
    readBool(KEYS.sidebarExpanded, true),
  );
  const [detailExpanded, setDetailExpanded] = useState(() =>
    readBool(KEYS.detailExpanded, true),
  );
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    readWidth(KEYS.sidebarWidth, DEFAULT_SIDEBAR_W),
  );
  const [detailWidth, setDetailWidth] = useState(() =>
    readWidth(KEYS.detailWidth, DEFAULT_DETAIL_W),
  );

  const sidebarWidthRef = useRef(sidebarWidth);
  const detailWidthRef = useRef(detailWidth);
  sidebarWidthRef.current = sidebarWidth;
  detailWidthRef.current = detailWidth;

  const toggleSidebar = useCallback(() => {
    setSidebarExpanded((prev) => {
      const next = !prev;
      localStorage.setItem(KEYS.sidebarExpanded, String(next));
      return next;
    });
  }, []);

  const toggleDetail = useCallback(() => {
    setDetailExpanded((prev) => {
      const next = !prev;
      localStorage.setItem(KEYS.detailExpanded, String(next));
      return next;
    });
  }, []);

  const resizeSidebar = useCallback((width: number) => {
    setSidebarWidth(width);
    sidebarWidthRef.current = width;
  }, []);

  const resizeDetail = useCallback((width: number) => {
    setDetailWidth(width);
    detailWidthRef.current = width;
  }, []);

  const getSidebarWidth = useCallback(() => sidebarWidthRef.current, []);
  const getDetailWidth = useCallback(() => detailWidthRef.current, []);

  const persistSidebarWidth = useCallback(() => {
    localStorage.setItem(KEYS.sidebarWidth, String(sidebarWidthRef.current));
  }, []);

  const persistDetailWidth = useCallback(() => {
    localStorage.setItem(KEYS.detailWidth, String(detailWidthRef.current));
  }, []);

  return {
    sidebarExpanded,
    detailExpanded,
    sidebarWidth,
    detailWidth,
    toggleSidebar,
    toggleDetail,
    resizeSidebar,
    resizeDetail,
    getSidebarWidth,
    getDetailWidth,
    persistSidebarWidth,
    persistDetailWidth,
  };
}
