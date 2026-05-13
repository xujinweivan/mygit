import pyautogui
import time
import os
import ctypes
from datetime import datetime
from PIL import Image, ImageChops, ImageStat

# --- 1. 路径与动态文件名生成 ---
current_script = os.path.abspath(__file__)
desktop = os.path.join(os.path.expanduser("~"), "Desktop")

# 动态文件名防止覆盖
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
file_name = f"网页抓取_{timestamp}.pdf"
save_path = os.path.join(desktop, file_name)

def get_similarity(img1, img2):
    """计算画面相似度"""
    diff = ImageChops.difference(img1, img2)
    stat = ImageStat.Stat(diff)
    diff_ratio = sum(stat.mean) / (3 * 255)
    return 1.0 - diff_ratio

def msg_box(title, text):
    """弹出 Windows 原生提示框"""
    ctypes.windll.user32.MessageBoxW(0, text, title, 64)

def start_mission():
    # --- 需求：仅修改此处的提示语，确保严格阻塞 ---
    print("=" * 75)
    print(f"📂 脚本位置: {current_script}")
    print(f"📄 落地文件: {save_path}")
    print("=" * 75)
    
    print("\n📋 操作说明：")
    print(" 1. 确认上述路径无误后，在此处按下 [回车键] 启动任务。")
    print(" 2. 脚本将倒计时 5 秒，请立即切换到网页并按 F11 进入全屏。")
    print(" 3. 【重要】进入全屏后，请务必用鼠标点击一下网页中心（激活焦点）。")
    print(" 4. 抓取完成后，脚本会自动按 F11 退出全屏并弹出完成提示。")
    print("-" * 75)

    # 💡 只有这里按了回车，才会往下走，绝对不抢跑
    input("\n👉 我已明白指令，按 [回车键] 开始倒计时...")

    print("\n🚀 5 秒倒计时开始，请操作网页（F11 + 点击中心）...")
    for i in range(5, 0, -1):
        print(f"⌛ {i}...")
        time.sleep(1)

    _, h = pyautogui.size()
    scroll_amount = -int(h * 0.9)
    
    captured_images = []
    last_img = None
    page = 1
    stop_count = 0 

    print("\n▶️ 正在自动检测网页底部（阈值：99.9%）...")

    try:
        while True:
            curr_raw = pyautogui.screenshot()
            curr_img = curr_raw.convert('RGB')
            
            # --- 核心判定逻辑（保持不变） ---
            if last_img is not None:
                similarity = get_similarity(last_img, curr_img)
                print(f"✅ 已抓取第 {page} 页... (相似度: {similarity:.4%})", end='\r')
                
                if similarity >= 0.999: 
                    stop_count += 1
                    if stop_count >= 2: 
                        print(f"\n🏁 已检测到网页到底。")
                        break
                else:
                    stop_count = 0 
            
            captured_images.append(curr_img)
            last_img = curr_img
            pyautogui.scroll(scroll_amount)
            
            time.sleep(1.2) 
            page += 1
            
    except KeyboardInterrupt:
        print("\n🛑 用户手动停止。")

    # --- 落地与反馈逻辑 ---
    if captured_images:
        print(f"\n💾 正在合成 {len(captured_images)} 页 PDF...")
        try:
            # 强制 PDF 格式保存，解决环境 JPEG 报错
            captured_images[0].save(
                save_path, 
                save_all=True, 
                append_images=captured_images[1:],
                format="PDF"
            )
            
            # 自动执行退出动作
            print("🚀 正在退出全屏并弹出通知...")
            pyautogui.press('f11') 
            time.sleep(0.5)
            
            msg_box("任务完成", f"PDF 已成功生成！\n文件名：{file_name}\n系统已自动退出全屏。")
            print(f"✨ 落地成功：{file_name}")
            
        except Exception as e:
            print(f"\n❌ 保存失败: {e}")
    else:
        print("\n❌ 未捕获到内容。")

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    start_mission()