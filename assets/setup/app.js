(() => {
  "use strict";

  const query = new URLSearchParams(window.location.search);
  const token = query.get("token") || "";
  if (token) {
    window.history.replaceState({}, document.title, "/");
  }

  const elements = {
    form: document.getElementById("setupForm"),
    apiKey: document.getElementById("apiKey"),
    revealKey: document.getElementById("revealKey"),
    installButton: document.getElementById("installButton"),
    buttonLabel: document.querySelector(".button-label"),
    formMessage: document.getElementById("formMessage"),
    setupView: document.getElementById("setupView"),
    successView: document.getElementById("successView"),
    deviceState: document.getElementById("deviceState"),
    deviceStateText: document.getElementById("deviceStateText"),
    environmentText: document.getElementById("environmentText"),
    routeList: document.getElementById("routeList"),
    steps: Array.from(document.querySelectorAll(".route-step")),
    installedNote: document.getElementById("installedNote"),
    showRestore: document.getElementById("showRestore"),
    restoreConfirm: document.getElementById("restoreConfirm"),
    cancelRestore: document.getElementById("cancelRestore"),
    restoreButton: document.getElementById("restoreButton"),
  };

  let progressTimer = null;

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Qwen-Setup-Token": token,
        ...(options.headers || {}),
      },
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "操作没有完成，请重试。 ");
    }
    return result;
  }

  function setDeviceState(kind, text) {
    elements.deviceState.classList.remove("is-ready", "is-error");
    if (kind) elements.deviceState.classList.add(kind);
    elements.deviceStateText.textContent = text;
  }

  function setProgress(step) {
    const progress = Math.max(0, Math.min(100, ((step - 1) / 3) * 100));
    elements.routeList.style.setProperty("--route-progress", String(progress / 100));
    elements.steps.forEach((item, index) => {
      item.classList.toggle("is-done", index + 1 < step);
      item.classList.toggle("is-active", index + 1 === step);
    });
  }

  function startProgress() {
    let step = 2;
    setProgress(step);
    progressTimer = window.setInterval(() => {
      if (step < 3) {
        step += 1;
        setProgress(step);
      }
    }, 1800);
  }

  function stopProgress(success) {
    window.clearInterval(progressTimer);
    progressTimer = null;
    setProgress(success ? 4 : 1);
  }

  function setLoading(loading) {
    elements.apiKey.disabled = loading;
    elements.revealKey.disabled = loading;
    elements.installButton.disabled = loading;
    elements.installButton.classList.toggle("is-loading", loading);
    elements.buttonLabel.textContent = loading ? "正在检测并配置…" : "立即接入 Codex";
  }

  async function loadStatus() {
    try {
      const result = await request("/api/status", { method: "GET" });
      if (result.codex_detected) {
        setDeviceState("is-ready", "已识别 Codex");
        elements.environmentText.textContent = "Codex 已就绪 · 配置会自动备份";
        setProgress(2);
      } else {
        setDeviceState("is-ready", "设置已就绪");
        elements.environmentText.textContent = "Codex 配置目录已就绪 · 配置会自动备份";
        setProgress(2);
      }
      if (result.installed) {
        elements.installedNote.hidden = false;
        elements.buttonLabel.textContent = "更新 Codex 配置";
      }
    } catch (error) {
      setDeviceState("is-error", "设置页已失效");
      elements.formMessage.textContent = error.message;
      elements.installButton.disabled = true;
    }
  }

  elements.revealKey.addEventListener("click", () => {
    const visible = elements.apiKey.type === "text";
    elements.apiKey.type = visible ? "password" : "text";
    elements.revealKey.textContent = visible ? "显示" : "隐藏";
    elements.revealKey.setAttribute("aria-label", visible ? "显示 API Key" : "隐藏 API Key");
    elements.apiKey.focus();
  });

  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const apiKey = elements.apiKey.value.trim();
    elements.formMessage.textContent = "";
    if (apiKey.length < 8) {
      elements.formMessage.textContent = "请粘贴完整的阿里云百炼 API Key。";
      elements.apiKey.focus();
      return;
    }
    setLoading(true);
    startProgress();
    try {
      await request("/api/install", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      });
      elements.apiKey.value = "";
      stopProgress(true);
      setDeviceState("is-ready", "千问已接入");
      elements.setupView.hidden = true;
      elements.successView.hidden = false;
      elements.successView.focus();
    } catch (error) {
      stopProgress(false);
      elements.formMessage.textContent = error.message;
      elements.apiKey.focus();
    } finally {
      setLoading(false);
    }
  });

  elements.showRestore.addEventListener("click", () => {
    elements.restoreConfirm.hidden = false;
    elements.showRestore.hidden = true;
    elements.cancelRestore.focus();
  });

  elements.cancelRestore.addEventListener("click", () => {
    elements.restoreConfirm.hidden = true;
    elements.showRestore.hidden = false;
    elements.showRestore.focus();
  });

  elements.restoreButton.addEventListener("click", async () => {
    elements.restoreButton.disabled = true;
    try {
      await request("/api/uninstall", { method: "POST", body: "{}" });
      elements.installedNote.hidden = true;
      elements.restoreConfirm.hidden = true;
      elements.showRestore.hidden = false;
      elements.buttonLabel.textContent = "立即接入 Codex";
      elements.formMessage.textContent = "已恢复原来的 Codex 配置。重新打开 Codex 后生效。";
      setProgress(2);
    } catch (error) {
      elements.formMessage.textContent = error.message;
    } finally {
      elements.restoreButton.disabled = false;
    }
  });

  loadStatus();
})();
