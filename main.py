import discord
from discord.ext import commands, tasks
import json
import os  # 추가: 환경 변수 사용을 위함
from dotenv import load_dotenv  # 추가: .env 파일 로드를 위함
from datetime import datetime, timedelta

# 1. 설정
load_dotenv()  # .env 파일에 저장된 내용을 불러옵니다.
TOKEN = os.getenv('DISCORD_TOKEN') # 이제 토큰을 직접 적지 않고 환경 변수에서 가져옵니다
INACTIVE_ROLE_NAME = "D"
ACTIVE_ROLE_NAME = "A"   # 활동 중인 사람 역할 이름 (따옴표 포함 문자열로 관리)
CHECK_INTERVAL_DAYS = 14

ADMIN_CHANNEL_ID = 1437786580340441142 # 관리자 알림 채널 ID
MY_GUILD_ID = 1437683163957559340      # 서버 ID
RESET_DAY = 0  # 0: 월요일
RESET_HOUR = 0 # 리셋할 시간

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True # 메세지 권한 추가
bot = commands.Bot(command_prefix='!', intents=intents)

# 활동 기록 로드/저장 함수
def load_data():
    if os.path.exists("activity.json"):
        with open("activity.json", "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(data):
    with open("activity.json", "w") as f:
        json.dump(data, f, indent=4)

# 2. 음성 채널 입장 감지
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel is not None: # 채널에 들어왔을 때
        data = load_data()
        data[str(member.id)] = datetime.now().isoformat()
        save_data(data)
        
        # 역할 부여 로직 (수정됨)
        role = discord.utils.get(member.guild.roles, name=ACTIVE_ROLE_NAME)
        if role:
            await member.add_roles(role) # await 추가

# 3. 2주 주기 체크 스케줄러
@tasks.loop(hours=1)
async def management_task():
    now = datetime.now()
    guild = bot.get_guild(MY_GUILD_ID)
    if not guild: return

    # 리셋 1시간 전 예고 로직
    if now.weekday() == RESET_DAY and now.hour == (RESET_HOUR - 1) % 24:
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        inactive_role = discord.utils.get(guild.roles, name=INACTIVE_ROLE_NAME)
        active_role = discord.utils.get(guild.roles, name=ACTIVE_ROLE_NAME)
        
        data = load_data()
        warning_list = []

        for member in guild.members:
            if member.bot: continue
            last_active_str = data.get(str(member.id))
            is_inactive = False
            
            if last_active_str:
                last_active = datetime.fromisoformat(last_active_str)
                if now - last_active > timedelta(days=CHECK_INTERVAL_DAYS):
                    is_inactive = True
            else:
                is_inactive = True

            if is_inactive and inactive_role:
                await member.add_roles(inactive_role)
                if active_role:
                    await member.remove_roles(active_role)
                warning_list.append(member.display_name)

        if admin_channel and warning_list:
            await admin_channel.send(f"⏰ **리셋 1시간 전 알림**\n2주 미활동자 {len(warning_list)}명에게 '{INACTIVE_ROLE_NAME}' 역할을 부여했습니다.")

    # 실제 데이터 리셋 로직 (정각)
    if now.weekday() == RESET_DAY and now.hour == RESET_HOUR:
        save_data({})
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send("🧹 **2주 주기 리셋 완료**\n활동 데이터가 초기화되었습니다.")

@bot.event
async def on_ready():
    print(f'{bot.user}가 가동되었습니다!')

    # 1. 상태 설정 (활동 + 말풍선 합치기)
    # CustomActivity에서 emoji 인자가 가끔 에러를 내니, 안전하게 name에 합쳤습니다.
    activity_list = [
        discord.Activity(type=discord.ActivityType.watching, name="서버 인원 전수 조사"),
        discord.CustomActivity(name="연님을 위해서 24시간 일하는 중 🥵")
    ]
    
    try:
        await bot.change_presence(status=discord.Status.online, activities=activity_list)
        print("상태 메시지 설정 완료!")
    except Exception as e:
        print(f"상태 설정 중 오류 발생: {e}")

    # ... 이후 전수 조사 로직은 그대로 유지 ...
    data = load_data()
    # (생략)
    # 전수 조사 로직
    data = load_data()
    now = datetime.now().isoformat()
    guild = bot.get_guild(MY_GUILD_ID)
    
    if guild:
        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                if not member.bot:
                    data[str(member.id)] = now
                    role = discord.utils.get(guild.roles, name=ACTIVE_ROLE_NAME)
                    if role:
                        await member.add_roles(role)
        save_data(data)
        print("현재 접속자 전수 조사 완료!")

    if not management_task.is_running():
        management_task.start()

bot.run(TOKEN)