# polyoffset

## 题面（可直接粘贴）

多边形内缩/外扩。约束：偏移后面积随距离单调；自交时回退到安全距离而不是产生自交；凸多边形与鞋带公式对照（≤1e-6）；非法多边形报错；1 万次不超过 500 ms。验收：cd polyoffset && python -m pytest tests -q -k offset。

## 边界要求（评审侧隐藏用例判分）

- 并发安全
- 非有限输入分类报错
- 性能上界按题面

## 运行方式

```bash
cd polyoffset && python -m pytest tests -q
```

初始 15 failed。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图形渲染
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
