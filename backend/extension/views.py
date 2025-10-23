# backend/extent/views.py
import os
import time
import json
import tempfile
from pathlib import Path

import pyautogui
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view
from rest_framework.response import Response
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ===================== 配置参数 =====================
TARGET_WEBSTORE_URL = "https://chrome.google.com/webstore/detail/json-formatter/bcjindcccaagfpapjjmafapmmgkkhgoa"  # 测试下载链接
TARGET_EXTENSION_NAME = "JSON Formatter"
EXTENSION_INTERNAL_PAGE = "popup.html"

CHROMEDRIVER_PATH = None
LAUNCH_WAIT_SEC = 2
INJECT_TIMEOUT = 20
# ====================================================

def _get_extension_id_via_extensions_page(driver: webdriver.Chrome, extension_name: str):
    try:
        original_window = driver.current_window_handle
        driver.switch_to.new_window('tab')
        driver.get('chrome://extensions')
        time.sleep(1.5)

        script = """
            const extensionName = arguments[0];
            const manager = document.querySelector('extensions-manager');
            if (!manager) return null;
            const itemList = manager.shadowRoot.querySelector('extensions-item-list');
            if (!itemList) return null;
            const items = itemList.shadowRoot.querySelectorAll('extensions-item');
            for (const item of items) {
                const nameEl = item.shadowRoot.querySelector('#name');
                if (nameEl && nameEl.textContent.trim() === extensionName) {
                    return item.id;
                }
            }
            return null;
        """
        ext_id = driver.execute_script(script, extension_name)
        driver.close()
        driver.switch_to.window(original_window)
        return ext_id if isinstance(ext_id, str) else None
    except Exception:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        return None

def _dump_browser_logs(driver: webdriver.Chrome):
    logs = {}
    for log_type in ["browser", "driver"]:
        try:
            logs[log_type] = driver.get_log(log_type)
        except Exception as e:
            logs[log_type] = {"error": str(e)}
    return logs

def _wait_page_flag(driver: webdriver.Chrome, timeout=INJECT_TIMEOUT):
    deadline = time.time() + timeout
    last_state = None
    while time.time() < deadline:
        try:
            state = driver.execute_script("""
                return {
                    url: location.href, readyState: document.readyState,
                    hasFlag1: typeof window.__apiRunner !== 'undefined',
                    hasFlag2: typeof window.__contentScriptLoaded !== 'undefined',
                    metaReady: !!document.querySelector('meta[name="ext-ready"]'),
                };
            """)
            last_state = state
            if state.get("hasFlag1") or state.get("hasFlag2") or state.get("metaReady"):
                return {"ok": True, "state": state}
        except Exception:
            pass
        time.sleep(1)
    return {"ok": False, "state": last_state}

@require_GET
def launch_and_check_extension(request):
    result = { "status": "error", "detail": None, "browser_logs": None, "opened_url": None }
    driver = None
    try:
        chrome_opts = Options()
        stable_profile_dir = Path(tempfile.gettempdir()) / "chrome_profile_stable"
        stable_profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_opts.add_argument(f"--user-data-dir={str(stable_profile_dir)}")
        chrome_opts.add_argument("--profile-directory=Default")
        chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_opts.add_experimental_option("prefs", {"extensions": {"dev_mode": True}})

        driver = webdriver.Chrome(options=chrome_opts)
        time.sleep(LAUNCH_WAIT_SEC)

        driver.get(TARGET_WEBSTORE_URL)

        # Cookie 弹窗处理
        try:
            cookie_button_xpath = "//button[contains(., 'Accept') or contains(., 'Reject') or contains(., '同意') or contains(., '接受')]"
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, cookie_button_xpath))
            )
            cookie_button.click()
            time.sleep(1)
        except TimeoutException:
            pass

        # 点击 "添加到 Chrome"
        add_button_xpath = "/html/body/c-wiz/div/div/main/div/section[1]/section/div/div[1]/div[2]/div/button"
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, add_button_xpath))).click()

        # pyautogui 处理确认弹窗
        time.sleep(2)
        pyautogui.press('left')
        time.sleep(0.5)
        pyautogui.press('enter')

        # 等待插件安装后检测
        time.sleep(5)
        ext_id = _get_extension_id_via_extensions_page(driver, TARGET_EXTENSION_NAME)

        if not ext_id:
            raise RuntimeError("安装后，无法在 chrome://extensions 页面上找到插件。")

        # 修改部分：如果能找到插件，就认为安装成功，直接返回
        result["status"] = "ok"
        result["detail"] = {"extension_id": ext_id, "message": f"插件 {TARGET_EXTENSION_NAME} 安装成功"}
        result["browser_logs"] = _dump_browser_logs(driver)

        # 不再打开内部页面
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'indent': 2})

        # （原逻辑）
        target_url = f"chrome-extension://{ext_id}/{EXTENSION_INTERNAL_PAGE}"
        driver.get(target_url)
        result["opened_url"] = target_url

        wait_info = _wait_page_flag(driver, timeout=INJECT_TIMEOUT)
        logs = _dump_browser_logs(driver)

        result["status"] = "ok" if wait_info.get("ok") else "opened"
        result["detail"] = wait_info
        result["browser_logs"] = logs

    except Exception as e:
        import traceback
        traceback.print_exc()
        result["status"] = "exception"
        result["detail"] = {"error": str(e), "traceback": traceback.format_exc()}
        if driver:
            result["browser_logs"] = _dump_browser_logs(driver)

    return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'indent': 2})


