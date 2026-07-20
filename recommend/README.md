# CSCD 审稿人推荐

基于 CSCD 第三方接口的中文 Web 应用。

## 功能

- **关键词推荐审稿人**：调用 `/getPeerReviewers`，每次最多 100 位
- **检索前过滤**：排除机构、排除姓名、仅含邮箱
- **二次精确检索**：在结果内按姓名/机构/学科搜索，H 指数、排序
- **作者发文分析**：点击审稿人，通过 `/searchArticles` 加载其 CSCD 论文
  - 按年堆叠柱状图
  - 蓝色 = 第一作者，绿色 = 通讯作者，灰色 = 其他

## 启动

```bash
npm install
cp .env.example .env.local
# 填入 CSCD_API_CODE 或 CSCD_USER / CSCD_PASSWORD
npm run dev
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `CSCD_API_CODE` | ApiCode（推荐） |
| `CSCD_USER` / `CSCD_PASSWORD` | 自动获取 ApiCode |

## 说明

- 通讯作者：CSCD 文献接口未明确提供该字段，系统按末位作者或姓名标注符号推断
- 发文加载：每位作者最多分页拉取 1000 篇（20×50），受 API 配额限制
