"""Music MCP Server — 心情歌单推荐.

一个独立的 MCP server，对外暴露 `search_music` 工具。
小暖在对话中感知到用户的情绪后，可以调用此工具推荐合适的音乐/歌曲。

启动方式（本地开发）:
  python -m mindmate.tools.mcp_servers.music_server

配置（.env 的 MCP_SERVERS）:
  {"music": {"command": "python", "args": ["-m", "mindmate.tools.mcp_servers.music_server"]}}
"""

from __future__ import annotations

import random
import sys

# ---------------------------------------------------------------------------
# 歌单数据库 —— 按心情分类的歌曲/歌单推荐
# 实际产品可接入 Spotify API / 网易云音乐 API，这里用精选歌单作为示例
# ---------------------------------------------------------------------------

PlaylistT = dict[str, list[dict[str, str]]]

_PLAYLISTS: PlaylistT = {
    "平静": [
        {"name": "Weightless", "artist": "Marconi Union",
         "note": "科学验证最减压的乐曲之一，非常适合放松"},
        {"name": "Gymnopédie No.1", "artist": "Erik Satie",
         "note": "钢琴独奏，安静温柔，适合一个人听"},
        {"name": "Clair de Lune", "artist": "Debussy",
         "note": "月光般流淌的旋律，把心静下来"},
        {"name": "River Flows in You", "artist": "Yiruma",
         "note": "治愈系钢琴，很多人说听完会想哭但心里暖暖的"},
        {"name": "安和桥", "artist": "宋冬野",
         "note": "缓慢的民谣，像有人在旁边陪你坐着"},
        {"name": "Comptine d'un autre été", "artist": "Yann Tiersen",
         "note": "《天使爱美丽》配乐，简单温柔"},
        {"name": "The Night Me and Your Mama Met", "artist": "Childish Gambino",
         "note": "纯器乐，适合放空"},
    ],
    "难过": [
        {"name": "Someone Like You", "artist": "Adele",
         "note": "有时候哭出来反而好受一些——这首歌陪你"},
        {"name": "Fix You", "artist": "Coldplay",
         "note": "有人会在你坠落时接住你——至少这首歌会"},
        {"name": "Let It Be", "artist": "The Beatles",
         "note": "顺其自然吧，有些事不需要马上解决"},
        {"name": "夜空中最亮的星", "artist": "逃跑计划",
         "note": "抬头看一眼星星，你并不是一个人"},
        {"name": "Hurt", "artist": "Johnny Cash",
         "note": "低沉的嗓音，不用说话，听着就好"},
        {"name": "平凡之路", "artist": "朴树", "note": "慢慢走，不用跑"},
        {"name": "Imagine", "artist": "John Lennon",
         "note": "闭上眼睛想想那个你希望的世界"},
    ],
    "开心": [
        {"name": "Happy", "artist": "Pharrell Williams",
         "note": "开心的时候就要大声放出来！"},
        {"name": "Can't Stop the Feeling!", "artist": "Justin Timberlake",
         "note": "身体会不由自主跟着晃"},
        {"name": "阳光宅男", "artist": "周杰伦",
         "note": "每次听都忍不住笑出来"},
        {"name": "Uptown Funk", "artist": "Mark Ronson ft. Bruno Mars",
         "note": "根本坐不住，起来扭两下"},
        {"name": "Good Day", "artist": "IU",
         "note": "甜甜的，像春天的第一口冰淇淋"},
        {"name": "Happy Together", "artist": "The Turtles",
         "note": "经典的开心老歌，越听越阳光"},
    ],
    "焦虑": [
        {"name": "Spiegel im Spiegel", "artist": "Arvo Pärt",
         "note": "极简古典，像呼吸一样慢下来"},
        {"name": "Breathe Me", "artist": "Sia",
         "note": "你不是唯一一个紧张的人"},
        {"name": "Breathe (2 AM)", "artist": "Anna Nalick",
         "note": "凌晨两点深呼吸——这首歌就是为那一刻写的"},
        {"name": "Forever Young", "artist": "Bob Dylan",
         "note": "慢版，让人安心"},
        {"name": "Good Night", "artist": "The Beatles",
         "note": "像一首摇篮曲，把紧张的心节放慢"},
        {"name": "Peace Piece", "artist": "Bill Evans",
         "note": "爵士钢琴独奏，两个和弦循环，像心跳一样稳定"},
    ],
    "孤独": [
        {"name": "The Sound of Silence", "artist": "Simon & Garfunkel",
         "note": "有时候沉默也是一种陪伴"},
        {"name": "好久不见", "artist": "陈奕迅",
         "note": "即使一个人走在街上，这首歌让你觉得有人在等你"},
        {"name": "Mad World", "artist": "Gary Jules",
         "note": "安静的孤独感——不是坏的感觉，就是真实"},
        {"name": "Yesterday", "artist": "The Beatles",
         "note": "有时候回忆就是最好的陪伴"},
        {"name": "I'm Not the Only One", "artist": "Sam Smith",
         "note": "你不是一个人有这种感觉"},
    ],
    "需要动力": [
        {"name": "Eye of the Tiger", "artist": "Survivor",
         "note": "Rocky 的主题曲，你自己就是主角"},
        {"name": "Don't Stop Believin'", "artist": "Journey",
         "note": "别停下来，哪怕只是一小步"},
        {"name": "倔强", "artist": "五月天",
         "note": "就算失望不能绝望——这句就够了"},
        {"name": "Stronger", "artist": "Kanye West",
         "note": "那些没打倒你的，确实让你更强大"},
        {"name": "追梦赤子心", "artist": "GALA",
         "note": "就算跑调也要大声唱——活着就要这样"},
        {"name": "Fight Song", "artist": "Rachel Platten",
         "note": "这是你的战歌，哪怕很小声"},
    ],
    "失眠": [
        {"name": "Moonlight Sonata", "artist": "Beethoven",
         "note": "月光奏鸣曲第一乐章，慢得刚刚好"},
        {"name": "Nocturne in E-flat major, Op. 9 No. 2",
         "artist": "Chopin", "note": "肖邦夜曲，适合在床上闭着眼睛听"},
        {"name": "Sleep Walk", "artist": "Santo & Johnny",
         "note": "经典的睡前纯音乐"},
        {"name": "Clouds", "artist": "Luke Faulkner",
         "note": "轻钢琴，像云飘过"},
        {"name": "Lullaby", "artist": "Brahms",
         "note": "如果小时候有人给你唱过这首歌，现在再听一次吧"},
    ],
}

# 所有歌曲的扁平列表（供 "随机" 和 "全部" 查询）
_ALL_SONGS: list[dict[str, str]] = []
for _cat, _songs in _PLAYLISTS.items():
    for _s in _songs:
        _ALL_SONGS.append({
            "name": _s["name"], "artist": _s["artist"],
            "note": _s["note"], "category": _cat,
        })


# ---------------------------------------------------------------------------
# MCP Server 实现
# ---------------------------------------------------------------------------

def _build_stdio_server():
    """构建一个通过 stdio 通信的 MCP server."""
    try:
        from mcp.server import Server  # noqa: F811
    except ImportError:
        print("请先安装 mcp 包: pip install mcp[cli]", file=sys.stderr)
        sys.exit(1)

    server = Server("music-server")

    @server.list_tools()
    async def list_tools():
        moods = "、".join(sorted(_PLAYLISTS.keys()))
        return [
            {
                "name": "search_music",
                "description": (
                    "根据心情推荐音乐/歌曲。用户表达情绪后，根据情绪匹配合适的歌单。"
                    "适用场景：'心情不好想听歌''有没有治愈的音乐'"
                    "'失眠了有没有助眠的歌'等。"
                    f"可选心情类别：{moods}。也可以不指定心情，随机推荐一首。"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mood": {
                            "type": "string",
                            "description": (
                                f"用户当前心情，可选：{moods}。"
                                "不确定时传'随机'，系统会自动选一个。"
                            ),
                        },
                        "count": {
                            "type": "integer",
                            "description": "推荐几首（默认 2），最多 5 首",
                        },
                    },
                },
            }
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name != "search_music":
            return {"content": [{"type": "text", "text": f"未知工具: {name}"}]}

        mood = (arguments.get("mood") or "随机").strip()
        count = min(int(arguments.get("count") or 2), 5)

        # 选择歌单
        if mood == "随机":
            mood = random.choice(list(_PLAYLISTS.keys()))
        # 模糊匹配
        if mood not in _PLAYLISTS:
            for key in _PLAYLISTS:
                if key in mood or mood in key:
                    mood = key
                    break
            else:
                mood = random.choice(list(_PLAYLISTS.keys()))

        songs = _PLAYLISTS.get(mood, _ALL_SONGS[:count])
        selected = random.sample(songs, min(count, len(songs)))

        # 格式化推荐结果
        lines = [f"✨ 为你选了 {len(selected)} 首「{mood}」的歌：", ""]
        for i, s in enumerate(selected, 1):
            lines.append(f"{i}. 🎵 **{s['name']}** — {s['artist']}")
            lines.append(f"   _{s['note']}_")
            lines.append("")

        closings = {
            "难过": "💙 难过的时候就听歌吧，不用急着好起来。",
            "失眠": "🌙 闭上眼睛，让音乐带你慢慢入睡。",
            "孤独": "🤝 希望这些歌让你觉得——有人懂你。",
            "开心": "🎉 开心的时候音乐是最好的庆祝！",
            "焦虑": "🌿 放慢呼吸，一首歌的时间就会好一点。",
            "需要动力": "💪 你是你自己的英雄。",
        }
        if mood in closings:
            lines.append(closings[mood])

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    return server


async def main():
    """MCP server 入口 — stdio 模式."""
    server = _build_stdio_server()
    try:
        from mcp.server.stdio import stdio_server
    except ImportError:
        print("请先安装 mcp 包: pip install mcp[cli]", file=sys.stderr)
        sys.exit(1)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
