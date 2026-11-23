# spritecull

## 题面（可直接粘贴）

屏幕空间精灵裁剪与批处理。约束：裁剪结果与逐精灵包围盒测试一致；部分可见的精灵保留；批次按纹理分组且组数最小；10 万精灵不超过 300 ms；非法输入报错。验收：cd spritecull && python -m pytest tests -q -k sprite。

## 边界要求（评审侧隐藏用例判分）

- 并发安全
- 非有限输入分类报错
- 性能上界按题面

## 运行方式

```bash
cd spritecull && python -m pytest tests -q
```

初始 15 failed。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：游戏开发
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
