# curvature

## 题面（可直接粘贴）

曲线曲率与拐点。约束：曲率与解析式误差 ≤1e-4；拐点检测与曲率变号一致；退化点曲率报错或定义为 0；1 万点不超过 400 ms；并发安全。验收：cd curvature && python -m pytest tests -q -k curvature。

## 边界要求（评审侧隐藏用例判分）

- 并发安全
- 非有限输入分类报错
- 性能上界按题面

## 运行方式

```bash
cd curvature && python -m pytest tests -q
```

初始 15 failed。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图形渲染
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
