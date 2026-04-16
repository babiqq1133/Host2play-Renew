import os
import sys
import time
import random
import requests
import tempfile
from dotenv import load_dotenv
from xvfbwrapper import Xvfb
from DrissionPage import ChromiumPage, ChromiumOptions

try:
    import speech_recognition as sr
    from pydub import AudioSegment
except ImportError:
    pass

# ==============================================================================
# Telegram 通知模块
# ==============================================================================
def send_tg_message(token, chat_id, message):
    if not token or not chat_id:
        print("未配置 TG_TOKEN 或 TG_CHAT_ID，跳过通知。")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    safe_message = message.replace('<b>', '').replace('</b>', '')
    payload = {"chat_id": chat_id, "text": safe_message, "parse_mode": "None"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ Telegram 通知发送成功！")
    except Exception as e:
        print(f"❌ Telegram 通知请求异常: {e}")

# ==============================================================================
# 语音验证码破解模块
# ==============================================================================
class RecaptchaAudioSolver:
    def __init__(self, page):
        self.page = page
        self.log_func = print

    def log(self, msg):
        self.log_func(f"[Solver] {msg}")

    def human_type(self, ele, text):
        ele.click()
        time.sleep(random.uniform(0.1, 0.3))
        ele.clear()
        for char in text:
            ele.input(char, clear=False)
            time.sleep(random.uniform(0.08, 0.25))
        time.sleep(random.uniform(0.3, 0.8))

    def solve(self, bframe):
        self.log("🎧 启动音频验证码破解...")
        try:
            audio_btn = bframe.ele('#recaptcha-audio-button', timeout=3)
            if audio_btn:
                self.page.actions.move_to(audio_btn, duration=random.uniform(0.5, 1.2))
                time.sleep(random.uniform(0.2, 0.5))
                audio_btn.click()
                self.log("🖱️ 已点击音频按钮")
            else:
                self.log("❌ 未找到音频按钮")
                return False

            time.sleep(random.uniform(3, 5))

            src = None
            for attempt in range(4):
                src = self.get_audio_source(bframe)
                if src:
                    break
                self.log(f"⚠️ 第 {attempt+1} 次获取音频链接失败，刷新...")
                reload_btn = bframe.ele('#recaptcha-reload-button', timeout=2)
                if reload_btn:
                    reload_btn.click()
                time.sleep(random.uniform(4, 7))

            if not src:
                self.log("❌ 无法获取音频链接（可能 IP 被临时限制）")
                return False

            self.log("📥 下载并处理音频...")
            r = requests.get(src, timeout=15)
            with open("audio.mp3", 'wb') as f:
                f.write(r.content)

            sound = AudioSegment.from_mp3("audio.mp3")
            sound.export("audio.wav", format="wav")

            recognizer = sr.Recognizer()
            with sr.AudioFile("audio.wav") as source:
                audio_data = recognizer.record(source)
                key_text = recognizer.recognize_google(audio_data)
                self.log(f"🗣️ 识别结果: {key_text}")

            input_box = bframe.ele('#audio-response', timeout=3)
            if input_box:
                self.human_type(input_box, key_text)
                verify_btn = bframe.ele('#recaptcha-verify-button', timeout=2)
                if verify_btn:
                    verify_btn.click()
                    time.sleep(5)
                    err = bframe.ele('.rc-audiochallenge-error-message', timeout=1)
                    if err and err.states.is_displayed:
                        self.log(f"❌ 验证失败: {err.text}")
                        return False
                    return True
            return False

        except Exception as e:
            self.log(f"💥 音频破解异常: {e}")
            return False
        finally:
            for f in ["audio.mp3", "audio.wav"]:
                if os.path.exists(f):
                    os.remove(f)

    def get_audio_source(self, bframe):
        for selector in ['.rc-audiochallenge-ndownload-link', 'xpath://a[contains(@href,".mp3")]', '#audio-source']:
            try:
                ele = bframe.ele(selector, timeout=1)
                if ele:
                    return ele.attr('href') or ele.attr('src')
            except:
                pass
        return None

# ==============================================================================
# 核心续期函数
# ==============================================================================
def renew_host2play(url, proxy_url=None):
    vdisplay = Xvfb(width=1280, height=720, colordepth=24)
    vdisplay.start()

    success = False
    msg = "未知错误"
    page = None

    try:
        co = ChromiumOptions()
        co.set_browser_path('/usr/bin/google-chrome')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-setuid-sandbox')
        co.set_argument('--window-size=1280,720')
        co.headless(False)
        co.auto_port()

        # 随机 User-Agent + 反检测
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        ]
        co.set_argument('--user-agent', random.choice(ua_list))

        if proxy_url:
            print(f"🌐 使用代理: {proxy_url}")
            if "socks" in proxy_url.lower():
                co.set_argument('--proxy-server', proxy_url)
            else:
                if not proxy_url.startswith("http"):
                    proxy_url = f"http://{proxy_url}"
                co.set_proxy(proxy_url)

        page = ChromiumPage(co)

        # 注入反检测 JS
        page.add_init_js("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(p) {
                if (p === 37445) return 'Intel Inc.';
                if (p === 37446) return 'Intel(R) UHD Graphics 630';
                return getParameter.apply(this, [p]);
            };
        """)

        print(f"🌐 访问续期页面: {url}")
        page.get(url, retry=3)
        time.sleep(random.uniform(6, 10))

        # 简单清理广告/遮挡
        page.run_js("document.querySelectorAll('ins, iframe[src*=\"ads\"], .modal').forEach(el => el.remove());")

        # 点击 Renew 按钮（支持多种写法）
        for _ in range(2):
            renew_btn = page.ele('xpath://button[contains(text(),"Renew server") or contains(text(),"Renew")]', timeout=4)
            if renew_btn:
                page.actions.move_to(renew_btn, duration=0.8)
                renew_btn.click()
                time.sleep(random.uniform(4, 7))
                break
            time.sleep(2)

        # 处理 reCAPTCHA
        solved = False
        anchor_frame = page.get_frame('xpath://iframe[contains(@src,"recaptcha/api2/anchor")]', timeout=8)
        if anchor_frame:
            anchor = anchor_frame.ele('#recaptcha-anchor', timeout=5)
            if anchor:
                page.actions.move_to(anchor, duration=1.0)
                anchor.click()
                time.sleep(random.uniform(5, 8))

                if anchor.attr('aria-checked') == 'true':
                    print("✅ reCAPTCHA 自动通过")
                    solved = True
                else:
                    print("🎧 需要音频验证...")
                    bframe = page.get_frame('xpath://iframe[contains(@src,"recaptcha/api2/bframe")]', timeout=6)
                    if bframe:
                        solver = RecaptchaAudioSolver(page)
                        solved = solver.solve(bframe)

        if solved:
            final_btn = page.ele('xpath://button[normalize-space(text())="Renew"]', timeout=5)
            if final_btn:
                final_btn.click()
                time.sleep(8)
                msg = "🎉 host2play 续期成功！"
                success = True
            else:
                msg = "❌ 未找到最终 Renew 按钮"
        else:
            msg = "❌ reCAPTCHA 未通过"

    except Exception as e:
        msg = f"💥 运行异常: {str(e)[:150]}"
        print(msg)
    finally:
        if page:
            try: page.quit()
            except: pass
        vdisplay.stop()
        return success, msg


if __name__ == "__main__":
    load_dotenv()   # 支持本地 .env 文件调试

    renew_url = os.getenv("RENEW_URL")
    tg_token = os.getenv("TG_TOKEN")
    tg_chat_id = os.getenv("TG_CHAT_ID")
    proxy_url = os.getenv("PROXY")

    if not renew_url:
        print("❌ 缺少 RENEW_URL 环境变量")
        sys.exit(1)

    is_success, result_message = renew_host2play(renew_url, proxy_url)
    send_tg_message(tg_token, tg_chat_id, result_message)

    if not is_success:
        sys.exit(1)
