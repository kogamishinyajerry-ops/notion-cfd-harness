# v1.3.0 Requirements — Real-time Convergence Monitoring

## Active Requirements

### Real-time Monitoring (MON)

- [ ] **MON-01**: 仿真进程残差数据 WebSocket 推送（从 OpenFOAM 日志解析，≤500ms debounce）
- [ ] **MON-02**: Dashboard 实时残差曲线（Recharts LineChart，随迭代更新）
- [ ] **MON-03**: Job detail 页面收敛监控面板
- [ ] **MON-04**: 收敛完成后自动展示结果摘要（压力、速度、Y+）
- [ ] **MON-05**: Job abort 按钮（停止运行中仿真）
- [ ] **MON-06**: 收敛异常检测 + 告警（divergence detection）

## Future Requirements

- **MON-07**: 多 metric 叠加显示（U, V, W, P, continuity）
- **MON-08**: 3D 速度场/压力场可视化（ParaView Web）
- **MON-09**: 多 case 并行对比收敛曲线

## Out of Scope

- **MON-F1**: ParaView Web 集成（Phase 14+）
- **MON-F2**: 仿真中间参数调整（OpenFOAM mid-run modification，太复杂）
- **MON-F3**: 多 case 并行对比（Phase 15+）

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| MON-01 | 12 | ✅ Complete |
| MON-02 | 13 | ✅ Complete |
| MON-03 | 13 | ✅ Complete |
| MON-04 | 14 | 📋 Plans Ready |
| MON-05 | 12 | ✅ Complete |
| MON-06 | 14 | 📋 Plans Ready |
