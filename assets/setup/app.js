(() => {
  "use strict";

  const MODE_AGGREGATE = "aggregate";
  const query = new URLSearchParams(window.location.search);
  const token = query.get("token") || "";
  if (token) {
    window.history.replaceState({}, document.title, "/");
  }

  const elements = {
    form: document.getElementById("setupForm"),
    apiKey: document.getElementById("apiKey"),
    revealKey: document.getElementById("revealKey"),
    modeInputs: Array.from(document.querySelectorAll('input[name="mode"]')),
    installButton: document.getElementById("installButton"),
    buttonLabel: document.querySelector(".button-label"),
    formMessage: document.getElementById("formMessage"),
    setupView: document.getElementById("setupView"),
    successView: document.getElementById("successView"),
    successTitle: document.getElementById("successTitle"),
    successSummary: document.getElementById("successSummary"),
    restartNote: document.getElementById("restartNote"),
    deviceState: document.getElementById("deviceState"),
    deviceStateText: document.getElementById("deviceStateText"),
    environmentText: document.getElementById("environmentText"),
    routeList: document.getElementById("routeList"),
    steps: Array.from(document.querySelectorAll(".route-step")),
    installedNote: document.getElementById("installedNote"),
    installedTitle: document.getElementById("installedTitle"),
    installedText: document.getElementById("installedText"),
    showRestore: document.getElementById("showRestore"),
    restoreConfirm: document.getElementById("restoreConfirm"),
    cancelRestore: document.getElementById("cancelRestore"),
    restoreButton: document.getElementById("restoreButton"),
    modelCount: document.getElementById("modelCount"),
    modelList: document.getElementById("modelList"),
  };

  let catalogs = {};
  let installed = false;
  let installedMode = null;
  let loading = false;
  let loadingAction = "install";
  let ready = false;
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
      throw new Error(result.message || "操作没有完成，请重试。");
    }
    return result;
  }

  function selectedMode() {
    return elements.modeInputs.find((input) => input.checked)?.value || MODE_AGGREGATE;
  }

  function setSelectedMode(mode) {
    elements.modeInputs.forEach((input) => {
      input.checked = input.value === mode;
    });
  }

  function modeLabel(mode) {
    return catalogs[mode]?.label || (mode === MODE_AGGREGATE ? "聚合模型" : "仅千问");
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
    setProgress(success ? 4 : 2);
  }

  function updateButtonLabel() {
    if (loading) {
      elements.buttonLabel.textContent =
        loadingAction === "restore" ? "正在恢复原配置…" : "正在检测并配置…";
      return;
    }
    const mode = selectedMode();
    if (!installed) {
      elements.buttonLabel.textContent = mode === MODE_AGGREGATE ? "接入全部模型" : "只接入千问";
      return;
    }
    if (mode === installedMode) {
      elements.buttonLabel.textContent = "更新当前配置";
    } else {
      elements.buttonLabel.textContent = mode === MODE_AGGREGATE ? "升级为聚合模型" : "切换为仅千问";
    }
  }

  function renderModels(mode) {
    const models = catalogs[mode]?.models || [];
    elements.modelList.replaceChildren();
    if (!models.length) {
      const empty = document.createElement("li");
      empty.className = "model-empty";
      empty.textContent = "模型目录正在准备…";
      elements.modelList.appendChild(empty);
      elements.modelCount.textContent = "正在读取…";
      return;
    }
    const fragment = document.createDocumentFragment();
    models.forEach((model) => {
      const item = document.createElement("li");
      const name = document.createElement("strong");
      const description = document.createElement("span");
      name.textContent = model.display_name;
      description.textContent = model.description;
      item.append(name, description);
      fragment.appendChild(item);
    });
    elements.modelList.appendChild(fragment);
    elements.modelCount.textContent = `${models.length} 个模型`;
  }

  function renderInstalledNote() {
    elements.installedNote.hidden = !installed;
    if (!installed) return;
    elements.installedTitle.textContent = `当前已接入：${modeLabel(installedMode)}`;
    elements.installedText.textContent =
      "重新输入 Key 可更新凭据；切换模式只会替换本工具的模型列表，不影响其他 Codex 设置。";
  }

  function renderMode() {
    renderModels(selectedMode());
    renderInstalledNote();
    updateButtonLabel();
  }

  function setLoading(isLoading, action = "install") {
    loading = isLoading;
    loadingAction = action;
    elements.apiKey.disabled = isLoading;
    elements.revealKey.disabled = isLoading;
    elements.modeInputs.forEach((input) => {
      input.disabled = isLoading;
    });
    elements.installButton.disabled = isLoading || !ready;
    elements.installButton.classList.toggle("is-loading", isLoading);
    elements.showRestore.disabled = isLoading;
    elements.cancelRestore.disabled = isLoading;
    elements.restoreButton.disabled = isLoading;
    updateButtonLabel();
  }

  function renderSuccess(mode) {
    const modelCount = catalogs[mode]?.models?.length || 0;
    const otherCount = Math.max(0, modelCount - 1);
    elements.successTitle.textContent =
      mode === MODE_AGGREGATE ? "聚合模型已经接入 Codex" : "千问已经接入 Codex";
    elements.successSummary.textContent =
      "模型目录和 API Key 已保存到这台电脑。API Key 会直接用于连接阿里云百炼。";
    elements.restartNote.textContent = otherCount
      ? `重新打开后默认使用 Qwen 3.8 Max，可在模型菜单切换另外 ${otherCount} 个模型。`
      : "重新打开后默认使用 Qwen 3.8 Max。";
  }

  async function loadStatus() {
    try {
      const result = await request("/api/status", { method: "GET" });
      catalogs = result.catalogs || {};
      installed = Boolean(result.installed);
      installedMode = installed && catalogs[result.mode] ? result.mode : null;
      setSelectedMode(installedMode || MODE_AGGREGATE);
      if (result.codex_detected) {
        setDeviceState("is-ready", "已识别 Codex");
        elements.environmentText.textContent = "Codex 已就绪 · 配置会自动备份";
      } else {
        setDeviceState("is-ready", "设置已就绪");
        elements.environmentText.textContent = "Codex 配置目录已就绪 · 配置会自动备份";
      }
      setProgress(2);
      ready = true;
      setLoading(false);
      renderMode();
    } catch (error) {
      setDeviceState("is-error", "设置页已失效");
      elements.formMessage.textContent = error.message;
      ready = false;
      setLoading(false);
    }
  }

  elements.modeInputs.forEach((input) => {
    input.addEventListener("change", () => {
      elements.formMessage.textContent = "";
      renderMode();
    });
  });

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
    const mode = selectedMode();
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
        body: JSON.stringify({ api_key: apiKey, mode }),
      });
      elements.apiKey.value = "";
      installed = true;
      installedMode = mode;
      stopProgress(true);
      setDeviceState("is-ready", mode === MODE_AGGREGATE ? "聚合模型已接入" : "千问已接入");
      renderSuccess(mode);
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
    setLoading(true, "restore");
    try {
      await request("/api/uninstall", { method: "POST", body: "{}" });
      installed = false;
      installedMode = null;
      elements.restoreConfirm.hidden = true;
      elements.showRestore.hidden = false;
      elements.formMessage.textContent = "已恢复原来的 Codex 配置。重新打开 Codex 后生效。";
      setDeviceState("is-ready", "已恢复原配置");
      setProgress(2);
      renderMode();
    } catch (error) {
      elements.formMessage.textContent = error.message;
    } finally {
      setLoading(false);
    }
  });

  setLoading(false);
  loadStatus();
})();
