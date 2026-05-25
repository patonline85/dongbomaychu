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
EXCLUDE_DIRS = os.environ.get('EXCLUDE_DIRS', '')

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Bảo mật: Chỉ người có ID hợp lệ mới được ra lệnh
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập. Bạn không có quyền thực thi lệnh này.')
        return

    # 1. Tạm dừng các container Database (không bao gồm Ghost)
    if DB_CONTAINERS:
        await update.message.reply_text(f'⏸ Đang tạm dừng các container: {DB_CONTAINERS} để bảo vệ dữ liệu...')
        subprocess.run(f"docker stop {DB_CONTAINERS}", shell=True)

    # 2. Xây dựng lệnh loại trừ (Né thư mục Ghost)
    exclude_args = ""
    if EXCLUDE_DIRS:
        # Biến "ghost_content,ghost_mysql" thành "--exclude='ghost_content' --exclude='ghost_mysql'"
        excludes = [f"--exclude='{item.strip()}'" for item in EXCLUDE_DIRS.split(',') if item.strip()]
        exclude_args = " ".join(excludes)

    await update.message.reply_text(f'⏳ Đang đồng bộ sang máy chủ ({TARGET_IP})...\n🚫 Bỏ qua các thư mục: {EXCLUDE_DIRS}')
    
    # 3. Chạy Rsync
    cmd = f"rsync -avz --delete {exclude_args} -e 'ssh -o StrictHostKeyChecking=no' {SOURCE_DIR} root@{TARGET_IP}:{DEST_DIR}"
    
    try:
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if process.returncode == 0:
            await update.message.reply_text('✅ Đồng bộ Rsync hoàn tất!\n\nCác file đã xử lý:\n' + process.stdout[-700:])
            # --- [THÊM MỚI] BẮT ĐẦU ĐỒNG BỘ ẢNH TIN TỨC ---
            await update.message.reply_text(f'📸 Đang quét và đồng bộ Kho ẢNH Tin Tức...')
            # Lệnh Rsync đồng bộ thư mục uploads từ host_root sang thư mục /root/ máy chủ đích
            cmd_images = f"rsync -avz --delete -e 'ssh -o StrictHostKeyChecking=no' /host_root/tintuc_uploads/ root@{TARGET_IP}:/root/tintuc_uploads/"
            
            img_process = subprocess.run(cmd_images, shell=True, capture_output=True, text=True)
            if img_process.returncode == 0:
                await update.message.reply_text('✅ Đã sao lưu trọn bộ Hình ẢNH Tin Tức sang máy dự phòng!')
            else:
                await update.message.reply_text(f'⚠️ Lỗi đồng bộ Ảnh Tin Tức:\n{img_process.stderr[-300:]}')
            # --- KẾT THÚC THÊM MỚI ---
        else:
            await update.message.reply_text(f'❌ Lỗi đồng bộ:\n{process.stderr[-700:]}')
    except Exception as e:
        await update.message.reply_text(f'❌ Lỗi hệ thống: {str(e)}')

    # 4. Khởi động lại các container Database
    if DB_CONTAINERS:
        await update.message.reply_text(f'▶️ Đang khởi động lại các container: {DB_CONTAINERS}...')
        subprocess.run(f"docker start {DB_CONTAINERS}", shell=True)
        await update.message.reply_text('✅ Mọi dịch vụ đã hoạt động bình thường!')

async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập.')
        return

    await update.message.reply_text('🧹 Đang tiến hành dọn rác hệ thống và xóa Log Docker...')
    
    try:
        # Lấy thông số dung lượng ổ cứng TRƯỚC khi dọn
        before_cmd = "df -h /var/lib/docker/containers | awk 'NR==2 {print $4}'"
        df_before = subprocess.run(before_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        
        # Lệnh 1: Dọn rác Docker (image thừa, network rỗng)
        subprocess.run("docker system prune -a -f", shell=True)
        
        # Lệnh 2: Cắt giảm toàn bộ file log của Docker về 0 byte
        subprocess.run("truncate -s 0 /var/lib/docker/containers/*/*-json.log", shell=True)
        
        # Lấy thông số dung lượng ổ cứng SAU khi dọn
        df_after = subprocess.run(before_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        
        await update.message.reply_text(
            f'✅ <b>Dọn dẹp hoàn tất!</b>\n\n'
            f'💾 Dung lượng trống ban đầu: <b>{df_before}</b>\n'
            f'💾 Dung lượng trống hiện tại: <b>{df_after}</b>',
            parse_mode='HTML'
        )
    except Exception as e:
        await update.message.reply_text(f'❌ Lỗi hệ thống khi dọn dẹp: {str(e)}')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Bảo mật: Kiểm tra quyền
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text('⛔ Từ chối truy cập. Bạn không có quyền thực thi lệnh này.')
        return

    await update.message.reply_text('📊 Đang thu thập dữ liệu hệ thống (CPU, RAM, Docker, USB)...')
    
    try:
        # Lấy thông số CPU & RAM (Tương đương htop)
        cpu_cmd = "top -bn1 | grep 'Cpu(s)'"
        cpu_info = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        ram_info = subprocess.run("free -h", shell=True, capture_output=True, text=True).stdout.strip()
        
        # Lấy thông số Docker (Tương đương ctop)
        docker_cmd = "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'"
        docker_info = subprocess.run(docker_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        if not docker_info:
            docker_info = "Không có container nào đang chạy."

        # Lấy thông số Ổ cứng và USB đang kết nối
        disk_info = subprocess.run("df -h /", shell=True, capture_output=True, text=True).stdout.strip()
        usb_info = subprocess.run("lsusb", shell=True, capture_output=True, text=True).stdout.strip()
        if not usb_info:
            usb_info = "Không tìm thấy thiết bị USB nào."

        # Cấu trúc tin nhắn trả về bằng định dạng HTML (thẻ <pre> giúp giữ nguyên khoảng cách cột)
        msg = (
            f"<b>🖥 THÔNG SỐ HỆ THỐNG (HTOP)</b>\n"
            f"<pre>{cpu_info}\n\n{ram_info}</pre>\n\n"
            
            f"<b>🐳 TIẾN TRÌNH DOCKER (CTOP)</b>\n"
            f"<pre>{docker_info}</pre>\n\n"
            
            f"<b>💾 Ổ CỨNG & USB</b>\n"
            f"<b>Disk (Root):</b>\n<pre>{disk_info}</pre>\n"
            f"<b>USB Kết nối:</b>\n<pre>{usb_info}</pre>"
        )

        # Telegram giới hạn 4096 ký tự/tin nhắn, phòng trường hợp log quá dài
        if len(msg) > 4000:
            await update.message.reply_text(msg[:4000], parse_mode='HTML')
            await update.message.reply_text(msg[4000:], parse_mode='HTML')
        else:
            await update.message.reply_text(msg, parse_mode='HTML')

    except Exception as e:
        await update.message.reply_text(f'❌ Lỗi khi đọc thông số: {str(e)}')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Đăng ký lệnh cho Bot
    app.add_handler(CommandHandler("sync", sync_command))
    app.add_handler(CommandHandler("clean", clean_command))
    app.add_handler(CommandHandler("status", status_command))
    
    print("Bot Telegram Sync & Clean đã khởi động...")
    app.run_polling()
