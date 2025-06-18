# Canal 配置记录项目

## 📖 项目概述

本项目用于记录和管理 Canal 配置的修改变更。保存了 Canal 的原始配置（source-conf）和修改后的配置（conf），以及用于验证配置的测试脚本。

## 🔧 Canal 配置修改记录

### 配置文件变更概览

根据 .gitignore 过滤规则，需要关注的配置文件变更：

| 文件 | 状态 | 变更数量 | 主要影响 |
|------|------|----------|----------|
| `canal.properties` | ✅ 已修改 | 4 项变更 | 输出模式、Kafka 认证 |
| `example/instance.properties` | ✅ 已修改 | 3 项变更 | 数据源、过滤规则、Topic |
| `kafka_client_jaas.conf` | 🆕 新增 | 新文件 | Kafka SASL 认证配置 |
| `canal_local.properties` | ⚪ 无变更 | - | - |

### 详细配置变更对比

#### 1. canal.properties 主配置文件修改

**修改前 (source-conf) → 修改后 (conf)**

| 配置项 | 修改前 | 修改后 | 变更说明 |
|--------|--------|--------|----------|
| `canal.serverMode` | `tcp` | `kafka` | **关键变更**: 从 TCP 客户端模式改为 Kafka 消息队列模式 |
| `kafka.kerberos.jaas.file` | `../conf/kerberos/jaas.conf` | `../conf/kafka_client_jaas.conf` | 更新 JAAS 配置文件路径 |
| `kafka.sasl.jaas.config` | `# kafka.sasl.jaas.config = ...` (注释) | `kafka.sasl.jaas.config = org.apache.kafka.common.security.plain.PlainLoginModule required username="jc" password="jckafka";` | **启用 SASL 认证**: 从注释改为启用，认证方式改为 PLAIN |
| `kafka.sasl.mechanism` | `# kafka.sasl.mechanism = SCRAM-SHA-512` (注释) | `kafka.sasl.mechanism = PLAIN` | 启用 SASL 机制为 PLAIN |
| `kafka.security.protocol` | `# kafka.security.protocol = SASL_PLAINTEXT` (注释) | `kafka.security.protocol = SASL_PLAINTEXT` | 启用 SASL 安全协议 |

#### 2. example/instance.properties 实例配置文件修改

**修改前 (source-conf) → 修改后 (conf)**

| 配置项 | 修改前 | 修改后 | 变更说明 |
|--------|--------|--------|----------|
| `canal.instance.master.address` | `127.0.0.1:3306` | `localhost:13306` | **MySQL 连接**: 端口从标准 3306 改为 13306 |
| `canal.instance.filter.regex` | `.*\\..*` | `keji_dsp\\..*` | **数据库过滤**: 从监听所有数据库改为只监听 keji_dsp 数据库 |
| `canal.mq.topic` | `example` | `keji_dsp_binlog` | **Kafka Topic**: 从默认 topic 改为业务专用 topic |

#### 3. 新增文件: kafka_client_jaas.conf

**文件路径**: `conf/kafka_client_jaas.conf`
**作用**: Kafka SASL PLAIN 认证配置

```conf
KafkaServer {
    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="jc"
    password="jckafka"
    user_jc="jckafka";
};

KafkaClient {
    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="jc"
    password="jckafka";
};
```

### 配置修改的业务意义

#### 🎯 核心架构变更
1. **数据输出模式**: TCP → Kafka
   - **影响**: 从直连模式改为消息队列模式，提高系统解耦性
   - **优势**: 支持多消费者、更好的容错和扩展能力

2. **业务数据专业化**: 全库监听 → keji_dsp 专库监听
   - **影响**: 只同步 keji_dsp 数据库的变更，减少无关数据
   - **优势**: 提高性能，降低网络和存储开销

#### 🔐 安全性增强
3. **Kafka 认证机制**: 无认证 → SASL PLAIN 认证
   - **认证用户**: jc / jckafka
   - **安全协议**: SASL_PLAINTEXT
   - **影响**: 提高 Kafka 连接的安全性

#### ⚙️ 环境配置调整
4. **MySQL 端口**: 3306 → 13306
   - **可能原因**: 测试环境隔离或避免端口冲突
   - **影响**: 需要确保目标 MySQL 实例在 13306 端口运行

5. **数据路由**: example topic → keji_dsp_binlog topic
   - **影响**: 数据流向更加明确，便于下游系统识别和消费
   - **优势**: 避免不同业务数据混合

### 配置修改总结

| 变更类别 | 具体变更 | 系统影响 |
|----------|----------|----------|
| **输出架构** | TCP 客户端模式 → Kafka 消息队列模式 | 提高系统解耦性和可扩展性 |
| **数据范围** | 全库监听 → keji_dsp 专库监听 | 专业化配置，提高性能 |
| **安全认证** | 无认证 → SASL PLAIN 认证 | 增强 Kafka 连接安全性 |
| **连接配置** | 标准端口 3306 → 自定义端口 13306 | 环境隔离或避免冲突 |
| **数据路由** | 通用 topic → 业务专用 topic | 明确数据流向，便于管理 |

## 🧪 测试脚本说明

### test_scripts 目录作用

`test_scripts/` 目录包含用于验证 Canal 配置的集成测试脚本：

#### async_integration_test.py
- **功能**: 异步多事件集成测试脚本
- **作用**: 验证 Canal + Kafka 数据同步功能是否正常工作
- **测试内容**:
  - 执行数据库 CRUD 操作（用户、商品、订单等）
  - 监听 Kafka 消息队列接收同步数据
  - 实时统计同步率和延迟
  - 验证数据一致性

#### 使用方法
```bash
cd test_scripts
poetry install
eval $(poetry env activate)
python async_integration_test.py --duration 2
```

#### 测试验证的配置项
- MySQL 连接配置 (localhost:13306)
- Kafka 连接和 SASL 认证
- keji_dsp 数据库监听
- keji_dsp_binlog topic 消息接收

---

**项目目的**: 记录 Canal 配置变更，提供配置验证工具