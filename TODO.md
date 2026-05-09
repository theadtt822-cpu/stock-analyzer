# TODO: 仪表盘模板修复

## 当前问题
`templates/dashboard_v2.html` 页面卡在 "加载中…" spinner。

## JS 语法状态
- `node --check` 已通过 ✅（上一轮修复已解决大部分语法错误）
- 但页面渲染结果可能仍有问题，需实际浏览器验证

## 已知修复（已做）
1. 替换 table row stock-name onclick 为刷新/编辑/删除按钮（`&#39;` HTML实体）
2. 替换 card header stock-name onclick 为非点击文本 + 按钮
3. 替换 watchlist stock-name onclick 为非点击文本 + 刷新/删除按钮
4. 移除 `batchCheckReports()`、`regenerateReport()`、`rptEid()` 废弃函数
5. `reportLink()` 简化为返回空字符串
6. 移除 `rpt-icon`、`rpt-refresh`、`tech-row` 相关 HTML/CSS
7. 新增 `refreshStock()`、`refreshWlStock()` 个股刷新函数
8. 补上 JS 字符串拼接中缺少的引号

## 待验证/待修复
- [ ] **页面实际加载测试**: 访问 http://47.116.23.182:8082/tiantian/ 看是否不再转圈
- [ ] **F12 Console 检查**: 确认无运行时 JS 错误
- [ ] **按钮功能**: 刷新/编辑/删除按钮是否正常回调 API
- [ ] **`.bak*` 文件清理**: `templates/` 下有 6 个 `.bak*` 备份文件可以删除

## 服务器信息
- 仪表盘: `dashboard_server.py`, 端口 8082
- 报告服务器: `report_server.py`, 端口 8081
- systemd: `dashboard-server.service`
- 模板路径: `templates/dashboard_v2.html`
- 访问: http://47.116.23.182:8082/

## 用户
- 邓天天（老板）: `/tiantian/` URL路径
- 波波: `/bobo/` URL路径
