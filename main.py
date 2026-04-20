import discord
from discord.ext import commands, tasks
import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random

# 1. 설정 및 환경 변수
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN') 

INACTIVE_ROLE_NAME = "D"
ACTIVE_ROLE_NAME = "A"
ADMIN_CHANNEL_ID = 1437786580340441142 # 관리자 알림 채널 ID
MY_GUILD_ID = 1437683163957559340      # 서버 ID

RESET_DAY = 0  # 0: 월요일
RESET_HOUR = 0 # 리셋할 시간 (0시)

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 데이터 로드/저장 함수
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

# 2. 음성 채널 입장 감지 (1번 요구사항: 입장 시 A 역할 부여)
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel is not None:
        # 활동 기록 업데이트
        data = load_data()
        data[str(member.id)] = datetime.now().isoformat()
        save_data(data)
        
        # A 역할 부여
        role = discord.utils.get(member.guild.roles, name=ACTIVE_ROLE_NAME)
        if role and role not in member.roles:
            await member.add_roles(role)

# 3. 2주 주기 관리 스케줄러
@tasks.loop(hours=1)
async def management_task():
    now = datetime.now()
    
    # [중요] 격주 리셋을 위한 주차 계산 (ISO 주차 % 2 == 0 일 때 리셋)
    # 만약 이번 주가 아니라 다음 주부터 시작하고 싶다면 == 1로 변경하세요.
    is_reset_week = (now.isocalendar()[1] % 2 == 0)
    
    if not is_reset_week:
        return

    guild = bot.get_guild(MY_GUILD_ID)
    if not guild: return

    # A. 리셋 1시간 전 (2번 요구사항: A 없는 사람에게 D 부여 + 알림)
    if now.weekday() == RESET_DAY and now.hour == (RESET_HOUR - 1) % 24:
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        inactive_role = discord.utils.get(guild.roles, name=INACTIVE_ROLE_NAME)
        active_role = discord.utils.get(guild.roles, name=ACTIVE_ROLE_NAME)
        
        warning_count = 0
        for member in guild.members:
            if member.bot: continue
            # A 역할이 없는 사람에게 D 부여
            if active_role not in member.roles:
                if inactive_role:
                    await member.add_roles(inactive_role)
                    warning_count += 1

        if admin_channel:
            await admin_channel.send(f"⏰ **리셋 1시간 전 알림**\n미활동자 {warning_count}명에게 '{INACTIVE_ROLE_NAME}' 역할을 부여했습니다. 잠시 후 데이터가 리셋됩니다.")

    # B. 정각 리셋 (3번 요구사항: A 제거, 데이터 초기화, D는 유지)
    if now.weekday() == RESET_DAY and now.hour == RESET_HOUR:
        active_role = discord.utils.get(guild.roles, name=ACTIVE_ROLE_NAME)
        
        # 서버의 모든 멤버를 순회하며 A 역할만 제거
        if active_role:
            for member in guild.members:
                if active_role in member.roles:
                    await member.remove_roles(active_role)
        
        save_data({}) # 활동 데이터 초기화 (다시 1번부터 시작)
        
        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            await admin_channel.send("🧹 **2주 주기 리셋 완료**\n모든 'A' 역할을 회수했습니다. 새로운 2주 측정을 시작합니다!")

@bot.event
async def on_ready():
    print(f'{bot.user} 가동 시작!')
    
    # 상태 메시지 설정
    try:
        status_msg = discord.CustomActivity(name="연님을 위해서 24시간 일하는 중 🥵")
        await bot.change_presence(status=discord.Status.online, activity=status_msg)
    except:
        pass

    # 봇 켜질 때 음성 채널에 이미 들어와 있는 사람들 체크
    guild = bot.get_guild(MY_GUILD_ID)
    if guild:
        data = load_data()
        active_role = discord.utils.get(guild.roles, name=ACTIVE_ROLE_NAME)
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    data[str(member.id)] = datetime.now().isoformat()
                    if active_role: await member.add_roles(active_role)
        save_data(data)

    if not management_task.is_running():
        management_task.start()

@bot.command(name="오늘뭐먹지")
async def recommend_menu(ctx):
    menu_list = [
    # 한식 (20가지)
    "김치찌개", "된장찌개", "부대찌개", "순두부찌개", "제육볶음", 
    "불고기", "비빔밥", "닭갈비", "삼겹살", "소갈비찜", 
    "순대국밥", "뼈해장국", "설렁탕", "육개장", "닭볶음탕", 
    "보쌈", "족발", "냉면", "칼국수", "수제비",

    # 일식/중식 (20가지)
    "마라탕", "꿔바로우", "짜장면", "짬뽕", "볶음밥", 
    "탕수육", "양꼬치", "훠궈", "돈카츠", "가츠동", 
    "사케동", "텐동", "초밥", "라멘", "우동", 
    "소바", "규동", "야끼소바", "오코노미야끼", "샤브샤브",

    # 양식/기타 (20가지)
    "치즈피자", "페퍼로니피자", "포테이토피자", "알리오올리오", "까르보나라", 
    "토마토파스타", "리조또", "치즈버거", "치킨버거", "스테이크", 
    "후라이드치킨", "양념치킨", "간장치킨", "샌드위치", "샐러드", 
    "타코", "브리또", "쌀국수", "팟타이", "나시고랭","분짜", "반미", "포케"
]
    selected = random.choice(menu_list)
    
    embed = discord.Embed(title="🍴 오늘의 메뉴 추천", color=0xffcc00)
    embed.add_field(name="✨ 결정된 메뉴", value=f"**{selected}**")
    await ctx.send(embed=embed)

# 6. 대망의 마지막 줄!
bot.run(TOKEN)