import os
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get('TELEGRAM_TOKEN')
ALLOWED_USER_ID = int(os.environ.get('ALLOWED_USER_ID', 0))
TARGET_IP = '192.168.33.83'
SOURCE_DIR = '/data_to_sync/'
DEST_DIR = os.environ.get('DEST_DIR', '/var/lib/docker/volumes/')
DB_CONTAINERS = os.environ.get('DB_CONTAINERS', '')

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Bảo mật: Chỉ người có ID hợp lệ mới được ra lệnh
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập. Bạn không có quyền thực thi lệnh này.')
        return

    # 1. Tạm dừng Database và các container cần thiết
    if DB_CONTAINERS:
        await update.message.reply_text(f'⏸ Đang tạm dừng các container: {DB_CONTAINERS} để bảo vệ dữ liệu...')
        subprocess.run(f"docker stop {DB_CONTAINERS}", shell=True)

    # 2. Chạy Rsync
    await update.message.reply_text(f'⏳ Đang đồng bộ dữ liệu sang máy chủ 2 ({TARGET_IP})...')
    cmd = f"rsync -avz --delete -e 'ssh -o StrictHostKeyChecking=no' {SOURCE_DIR} root@{TARGET_IP}:{DEST_DIR}"
    
    try:
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if process.returncode == 0:
            await update.message.reply_text('✅ Đồng bộ Rsync hoàn tất!\n\nCác file đã xử lý:\n' + process.stdout[-700:])
        else:
            await update.message.reply_text(f'❌ Lỗi đồng bộ:\n{process.stderr[-700:]}')
    except Exception as e:
        await update.message.reply_text(f'❌ Lỗi hệ thống: {str(e)}')

    # 3. Khởi động lại Database
    if DB_CONTAINERS:
        await update.message.reply_text(f'▶️ Đang khởi động lại các container: {DB_CONTAINERS}...')
        subprocess.run(f"docker start {DB_CONTAINERS}", shell=True)
        await update.message.reply_text('✅ Mọi dịch vụ đã hoạt động bình thường!')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("sync", sync_command))
    print("Bot Telegram Sync đã khởi động...")
    app.run_polling()