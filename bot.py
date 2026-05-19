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

# --- LỆNH ĐỒNG BỘ HIỆN TẠI ---
async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập. Bạn không có quyền thực thi lệnh này.')
        return

    if DB_CONTAINERS:
        await update.message.reply_text(f'⏸ Đang tạm dừng các container: {DB_CONTAINERS} để bảo vệ dữ liệu...')
        subprocess.run(f"docker stop {DB_CONTAINERS}", shell=True)

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

    if DB_CONTAINERS:
        await update.message.reply_text(f'▶️ Đang khởi động lại các container: {DB_CONTAINERS}...')
        subprocess.run(f"docker start {DB_CONTAINERS}", shell=True)
        await update.message.reply_text('✅ Mọi dịch vụ đã hoạt động bình thường!')

# --- LỆNH DỌN DẸP MỚI THÊM ---
async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập.')
        return

    await update.message.reply_text('🧹 Đang tiến hành dọn rác và xóa Log Docker...')
    
    try:
        # Lấy dung lượng ổ cứng trước khi dọn
        before_cmd = "df -h /var/lib/docker/containers | awk 'NR==2 {print $4}'"
        df_before = subprocess.run(before_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        
        # 1. Dọn rác Docker (thêm -f để tự động Yes)
        subprocess.run("docker system prune -a -f", shell=True)
        
        # 2. Cắt giảm toàn bộ file log của Docker về 0 byte
        subprocess.run("truncate -s 0 /var/lib/docker/containers/*/*-json.log", shell=True)
        
        # Lấy dung lượng ổ cứng sau khi dọn
        df_after = subprocess.run(before_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        
        await update.message.reply_text(
            f'✅ <b>Dọn dẹp hoàn tất!</b>\n\n'
            f'💾 Dung lượng trống ban đầu: <b>{df_before}</b>\n'
            f'💾 Dung lượng trống hiện tại: <b>{df_after}</b>',
            parse_mode='HTML'
        )

    except Exception as e:
        await update.message.reply_text(f'❌ Lỗi hệ thống khi dọn dẹp: {str(e)}')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Đăng ký các lệnh
    app.add_handler(CommandHandler("sync", sync_command))
    app.add_handler(CommandHandler("clean", clean_command))
    
    print("Bot Telegram Sync & Clean đã khởi động...")
    app.run_polling()
