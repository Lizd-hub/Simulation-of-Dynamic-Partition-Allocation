# 动态分区分配模拟

本项目使用 Python 实现动态分区存储管理的四种经典算法，并提供一个轻量级网页用于并行可视化比较：

- `First Fit`
- `Best Fit`
- `Worst Fit`
- `Next Fit`

核心特性：

- 使用链表维护空闲分区与已分配分区。
- 统一事件流驱动四种算法，便于横向对比。
- 实时展示内存块分布、失败次数、利用率、空闲块数量与分布情况。
- 为每个算法输出带时间戳的 CSV 日志，便于实验报告整理。

## 运行方式

在项目根目录执行：

```powershell
python app.py
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## 目录说明

- [app.py](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\app.py)：Web 服务入口。
- [algorithms](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\algorithms)：四种算法与链表基础结构。
- [simulation](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\simulation)：统一仿真调度与 CSV 日志模块。
- [static](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\static)：前端页面、样式与交互脚本。
- [tests](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\tests)：基础回归测试。
- [logs](C:\Users\26943\Desktop\OS_experiment\Simulation of Dynamic Partition Allocation\logs)：运行时生成的日志文件目录。

## 测试

```powershell
python -m unittest discover -s tests -v
```

