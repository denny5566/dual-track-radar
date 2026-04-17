import json
import os
from pathlib import Path
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

WEB_DATA_DIR = Path(__file__).parent / "web" / "public" / "data"
WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = [
    {
        "date": "2026-04-14",
        "topic": "美股超級財報週開跑，銀行股獲利超乎預期，台股盤整守住萬二關卡。",
    },
    {
        "date": "2026-04-15",
        "topic": "台積電強勢法說會前瞻，中東地緣政治稍微降溫，油價回落。",
    },
    {
        "date": "2026-04-16",
        "topic": "油價再度衝破100美元通膨失控vs短線技術樂觀，台積電法說成關鍵轉折點。",
    }
]

SYSTEM = """你是一台生成符合嚴格 JSON 格式的模擬爬蟲系統。
請根據給定的主題與日期，生成一篇非常逼真的財經雙軌報告。
必須輸出「純 JSON 字串」，且符合以下 Schema：
{
  "meta": { "date": "YYYY-MM-DD" },
  "daily_focus": "100字焦點摘要",
  "clash_or_sync": "描述群益與庭瀠觀點撞擊",
  "investor_reminder": "投資提醒",
  "article": {
    "title": "新聞標題",
    "sections": [
      {"heading": "段落標題", "content": "段落內容"}
    ],
    "tags": ["#標籤1", "#標籤2"]
  },
  "top5_news": [
    {"headline": "新聞1標題", "summary": "新聞1摘要"}
  ],
  "comparison": {
    "capital_futures": {"sentiment": "中性偏多", "key_levels": "萬二關卡", "main_points": ["要點1", "要點2", "要點3"]},
    "yu_ting_hao": {"sentiment": "保守悲觀", "key_levels": "通膨與殖利率", "main_points": ["要點A", "要點B", "要點C"]}
  }
}
請勿輸出任何 markdown code block, 只輸出 JSON。"""

def generate():
    for p in PROMPTS:
        print(f"Generating for {p['date']}...")
        ans = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            temperature=0.7,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"請生成日期為 {p['date']}，主題為：{p['topic']} 的 JSON"}]
        )
        text = ans.content[0].text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        
        try:
            data = json.loads(text)
            date_key = p['date'].replace("-", "")
            out_path = WEB_DATA_DIR / f"{date_key}.json"
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if p['date'] == "2026-04-16":
                (WEB_DATA_DIR / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved {out_path.name}")
        except Exception as e:
            print(f"Error parsing JSON for {p['date']}: {e}")

if __name__ == "__main__":
    generate()
