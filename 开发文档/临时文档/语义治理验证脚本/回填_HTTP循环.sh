#!/bin/bash
# 语义打齐回填循环(HTTP调后端常驻服务,永不暴毙)
# 用法: screen -dmS 回填 bash 回填_HTTP循环.sh
BASE="/Users/hekunhua/Documents/Agent/PHP/华世王镞_v2"
BATCH=20    # 每次处理条数(gate=true含少量LLM调用,20条安全不超时)
GATE=true   # 护栏8全开:长上下文走deepseek证据驱动裁定(精度第一,一锤子买卖,不留尾巴)
SHARD=0     # 分片号(并行时改)
SHARDS=1    # 总分片数
LOG="$BASE/开发文档/临时文档/语义治理验证脚本/回填_HTTP.log"
# 启动时用后端函数生成有效token(带正确session_version)
TOKEN=$(cd "$BASE" && backend/venv/bin/python3.14 -c "
import asyncio,sys; sys.path.insert(0,'backend'); sys.path.insert(0,'.')
from app.services.auth import create_access_token, get_user_by_id
from app.database import AsyncSessionLocal
async def m():
    async with AsyncSessionLocal() as db:
        u = await get_user_by_id(db, 4)
        sv = getattr(u, 'session_version', 0) if u else 0
    print(create_access_token(4, 'admin', sv))
asyncio.run(m())
" 2>/dev/null | tail -1)

echo "[$(date)] 回填启动 batch=$BATCH gate=$GATE shard=$SHARD/$SHARDS" | tee -a "$LOG"

while true; do
    RESULT=$(curl -s --max-time 120 -X POST http://127.0.0.1:33000/api/modules/call \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"target_module\":\"knowledge\",\"action\":\"align_entity_batch\",\"parameters\":{\"batch\":$BATCH,\"gate\":$GATE,\"shard\":$SHARD,\"shards\":$SHARDS}}")

    # 用 grep/sed 提取(不依赖 python 路径)
    CHECKED=$(echo "$RESULT" | grep -o '"checked":[0-9]*' | grep -o '[0-9]*')
    ALIGNED=$(echo "$RESULT" | grep -o '"aligned":[0-9]*' | grep -o '[0-9]*')
    REMAINING=$(echo "$RESULT" | grep -o '"remaining":[0-9]*' | grep -o '[0-9]*')

    echo "[$(date)] 查${CHECKED:-?} 合并${ALIGNED:-?} 剩${REMAINING:-?}" | tee -a "$LOG"

    if [ "$REMAINING" = "0" ]; then
        echo "[$(date)] ★ 全部完成!" | tee -a "$LOG"
        break
    fi
    if [ -z "$CHECKED" ]; then
        echo "[$(date)] ⚠️ 返回异常,休息30秒: $(echo $RESULT | head -c 200)" | tee -a "$LOG"
        sleep 30
    fi
done
