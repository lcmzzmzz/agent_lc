# EcomResearcher WebSocket 前后端编程详解

> 本文以本项目真实代码（后端 `backend/server/ecommerce_api.py` + 前端 `frontend/ecommerce.html`）讲解 WebSocket 的前后端编程，可对照源码阅读。

---

## 1. WebSocket 是什么，为什么用它

**HTTP** 是「一问一答」：前端发请求 → 后端算完 → 一次性返回。中间没法说话。

**WebSocket** 是「建立一条持久双向通道」：连上之后，前后端随时互发消息，直到一方关闭。

本项目的选品研究流程要跑 30 秒~几分钟，用户需要看实时进度（规划完成 → 研究中 → 评分中...）。HTTP 做不到（只能干等），WebSocket 可以一边跑一边推。所以研究页选了 WS。

---

## 2. 后端编程（FastAPI）

核心代码 `backend/server/ecommerce_api.py:70`：

```python
@router.websocket("/ws/ecommerce")          # ① 装饰器：声明这是个 WS 端点
async def ecommerce_websocket(websocket: WebSocket):
    await websocket.accept()                 # ② 握手：接受连接
    try:
        data = await websocket.receive_json()  # ③ 阻塞等前端发来的第一条消息
        query = data.get("query")

        # ④ 关键技巧：把"往 WS 发消息"包成一个回调函数
        async def progress(event, payload):
            await websocket.send_json({"event": event, **payload})

        # ⑤ 跑业务，把这个回调传进去
        result = await run_ecommerce_research(
            query=query, ...,
            progress_callback=progress,      # 业务跑到某阶段就调 progress → 推给前端
        )
        # ⑥ 全部跑完，发最终结果
        await websocket.send_json({"event": "done", **_summarize(result)})

    except WebSocketDisconnect:              # ⑦ 前端主动断开
        logger.info("disconnected")
    except Exception as exc:                 # ⑧ 业务异常，回传错误（别让前端挂起）
        await websocket.send_json({"event": "error", "error": str(exc)})
    finally:
        await websocket.close()              # ⑨ 无论成功失败，最后都关连接
```

**逐点解释：**

| 步骤 | API | 作用 |
|------|-----|------|
| ① | `@router.websocket(path)` | 声明 WS 路由（区别于 `@router.post`） |
| ② | `await websocket.accept()` | 完成 WebSocket 握手，连接正式建立 |
| ③ | `await websocket.receive_json()` | 阻塞等前端消息（收到 `{query,...}`） |
| ④⑤ | **progress_callback** | **精髓**：业务函数不知道前端存在，它只知道「跑完一个阶段就调一下 callback」。后端把 `websocket.send_json` 包装成 callback 注入进去，于是业务跑到哪、前端就收到哪。这叫**依赖注入解耦** |
| ⑥ | `send_json({"event":"done",...})` | 推送最终完整结果 |
| ⑦ | `except WebSocketDisconnect` | 用户关页面/刷新会触发，要捕获（否则后端报错） |
| ⑧ | `except Exception` | 业务崩了也要告诉前端（否则前端一直转圈） |
| ⑨ | `finally: close()` | 兜底关闭，防止连接泄漏 |

**对应业务侧**（`graph.py`）：业务在每个阶段调 `progress_callback("planner_done", {...})`，这个调用最终就是后端的 `websocket.send_json`。业务和 WS 之间**只靠一个函数参数**耦合，非常干净。

> **当前架构下 WS 层完全稳定**：业务侧后续演进都不影响 WS 通信——
> - trend / competitor / review 的 summary 全部 LLM 化（DeepSeek 生成，规则兜底）
> - review 走**双数据源**（`review_scraper`：有 `APIFY_API_TOKEN` 时优先抓 Amazon/Reddit 真实评论，失败自动降级 Tavily）
> - 这些只让 `done` 事件的 payload 更丰富（多了 `review_result` / `evaluation_summary` / `review_source` 等字段，见第 5 节），WS 推进度/收结果的机制一文不变。

---

## 3. 前端编程（浏览器 WebSocket API）

核心代码 `frontend/ecommerce.html:221`：

```javascript
const ws = new WebSocket(`ws://${host}/ws/ecommerce`);  // ① 建连接

ws.onopen = () => {                                       // ② 连上了
  ws.send(JSON.stringify({                                //    立刻把表单数据发过去
    query, target_market, depth, use_llm
  }));
};

ws.onmessage = (evt) => {                                 // ③ 每收到一条消息
  const data = JSON.parse(evt.data);
  const event = data.event;
  if (event === "done") {                                 //    最终结果
    renderScore(data.opportunity_score);
    renderReport(data.report);
    ws.close();                                           //    用完主动关
  } else if (event === "error") {
    showError(data.error);
  } else {                                                //    进度事件
    addStage(event);                                      //    更新进度时间线
  }
};

ws.onerror = () => { showError("连接错误"); };             // ④ 连接出错
ws.onclose = () => { setConn("已断开"); };                // ⑤ 连接关闭
```

**浏览器 WebSocket 只有 4 个事件**，记住这 4 个就会了：

| 事件 | 触发时机 | 你在里面干嘛 |
|------|----------|--------------|
| `onopen` | 连接建立成功 | 发初始数据（query） |
| `onmessage` | **每收到一条消息** | 解析 + 按 `event` 分发渲染（核心） |
| `onerror` | 连接出错 | 提示用户 |
| `onclose` | 连接关闭（双方任一关闭） | 收尾（恢复按钮状态等） |

发消息用 `ws.send(JSON.stringify(...))`，收消息在 `onmessage` 里 `JSON.parse(evt.data)`。

---

## 4. 完整时序（端到端）

```
前端(浏览器)                          后端(FastAPI)
   │                                      │
   │  new WebSocket("ws://.../ws/ecommerce")│
   │──────────────────────────────────────▶│  ① TCP 握手
   │                                      │  await accept()
   │  onopen 触发                          │
   │  ws.send({query:"portable blender"}) │
   │──────────────────────────────────────▶│  ② receive_json() 收到
   │                                      │  开始 run_ecommerce_research()
   │                                      │  ├─ planner 跑完
   │  ◀────────── {"event":"planner_done"}│  ③ 推进度（progress_callback）
   │  onmessage → 更新进度时间线           │  ├─ 三路并发研究
   │  ◀────────── {"event":"research_done"}│  ④ 推进度
   │  onmessage → 更新进度                 │  ├─ 评分
   │  ◀────────── {"event":"scoring_done"}│  ⑤ 推进度
   │  ...继续推 report_done/quality_done  │  └─ 跑完
   │  ◀────────── {"event":"done", 报告..}│  ⑥ 推最终结果
   │  onmessage → 渲染报告/雷达图          │
   │  ws.close()                           │  finally close()
   │──────────────────────────────────────▶│  连接关闭
   │  onclose 触发                         │
```

---

## 5. 消息协议（前后端约定）

双向都发 JSON，统一用 `event` 字段分发：

| 方向 | 消息 | 说明 |
|------|------|------|
| 前端→后端 | `{query, target_market, platforms, depth, use_llm}` | onopen 时发一次（无 event 字段） |
| 后端→前端 | `{"event": "start" / "planner_done" / "research_running" / "research_done" / "scoring_done" / "report_done" / "quality_done", ...}` | 进度事件 |
| 后端→前端 | `{"event": "done", report, opportunity_score, quality_check, audit_log, trend_result, competitor_result, review_result, evaluation_summary, output_paths, ...}` | 最终完整结果（`_summarize` 汇总，含双数据源 `review_result.review_source` / `evaluation_summary.review_count` 等） |
| 后端→前端 | `{"event": "error", "error": "..."}` | 异常 |

前端 `onmessage` 里就是 `switch(data.event)`：`done` 渲染结果、`error` 报错、其它更新进度。

---

## 6. 容易踩的坑（本项目都处理了）

1. **后端必须捕获 `WebSocketDisconnect`**：用户关页面时前端断开，后端 `receive_json`/`send_json` 会抛异常，不捕获就 500。
2. **业务异常要回传**：`except Exception` 里发 `{"event":"error"}`，否则前端 `onmessage` 永远不触发、一直转圈。
3. **`finally close()`**：防止异常路径下连接没关、资源泄漏。
4. **前端拿到 `done` 后主动 `ws.close()`**：结果已收到，没必要保持连接。
5. **`onclose` 别和"出错"混淆**：代码里用 `connState` 文字判断（"完成"/"错误"才不算异常断开），避免正常关闭显示成"已断开"吓到用户。
6. **JSON 双向**：前端 `JSON.stringify` 发、`JSON.parse` 收；后端 `receive_json`/`send_json`。两边都约定 `{event, ...}` 结构，靠 `event` 字段分发。

---

## 7. 为什么用 WS 而不是别的

| 方案 | 能否实时进度 | 双向 | 复杂度 | 本项目是否适合 |
|------|------------|------|--------|---------------|
| HTTP POST（同步） | ❌ 只能等最终结果 | 否 | 低 | 适合脚本/批量（已提供 POST 端点） |
| HTTP 轮询 | ⚠️ 假实时（每隔 N 秒问一次） | 否 | 中 | 能用但浪费、体验差 |
| SSE（Server-Sent Events） | ✅ 服务端单向推 | 否（只能服务端→前端） | 中 | 本项目前端不发后续消息，SSE 其实也够；用 WS 是为留扩展余地 |
| **WebSocket** | ✅ 真·实时 | ✅ 双向 | 中 | **本项目选择**：研究页需要实时进度 |

> 补充：本项目前端连上后只发一次 query、之后只收消息，理论 SSE 就够。选 WS 主要是：(1) 语义上"双向通道"更贴切；(2) 未来若加"中途取消""追问"等前端→后端交互，WS 直接支持，SSE 要另搭。

---

## 8. 一句话总结

**后端**：`@websocket` + `accept / receive_json / send_json`，把 `send_json` 包成 callback 注入业务，业务跑到哪推到哪；**前端**：`new WebSocket` + 4 个事件，`onopen` 发请求、`onmessage` 按 event 渲染。两边通过 `{event, ...}` JSON 消息协议双向通信。
