![xiaodu_voice_control logo](./logo.svg)

# XiaoDu Voice Control

`xiaodu_voice_control` 是一个 Home Assistant 自定义集成，用来管理要暴露给小度的设备列表，并把设备、`botID`、`openUid` 和运行时配置同步到独立服务 `xiaodu_voice_control_service`。

本仓库适合通过 **HACS 自定义仓库** 安装。

## 版本信息

- 集成版本：`1.0.0`
- HACS 最低 Home Assistant 版本：`2024.1.0`

## 功能概览

- 在 HA 侧边栏提供“`小度语音设备`”管理页面
- 图形化增删改要暴露给小度的设备
- 同步设备到独立服务容器
- 维护小度技能参数：
  - `botID`
  - `ClientSecret`
  - `openUid`
  - `internal_api_token`
- 代理小度 OAuth / 发现 / 控制 / 查询接口到独立服务

## 项目结构

```text
xiaodu_voice_control/
├─ custom_components/
│  └─ xiaodu_voice_control/
├─ examples/
│  ├─ configuration.yaml.snippet
│  └─ xiaodu_voice_control.yaml.example
├─ hacs.json
└─ README.md
```

## 推荐部署顺序

建议严格按下面顺序操作：

1. 先部署独立服务 `xiaodu_voice_control_service`
2. 再通过 HACS 安装本集成
3. 重启 Home Assistant
4. 打开 HA 侧边栏“`小度语音设备`”
5. 配置服务参数、添加设备、同步设备
6. 最后到小度技能平台完成授权和测试

## 一、先部署独立服务

本集成依赖独立服务容器 `xiaodu_voice_control_service`。

- GitHub 仓库：[demon3434/xiaodu_voice_control_service](https://github.com/demon3434/xiaodu_voice_control_service)
- Docker Hub 镜像：[demon3434/xiaodu_voice_control_service](https://hub.docker.com/r/demon3434/xiaodu_voice_control_service)

推荐直接拉取镜像：

```bash
docker pull demon3434/xiaodu_voice_control_service:latest
```

如果服务部署完成，并且浏览器能打开：

```text
http://你的服务地址:8129/
```

就可以继续安装本集成。

## 二、通过 HACS 安装

### 方式 1：添加为 HACS 自定义仓库

1. 打开 HACS。
2. 进入“集成”。
3. 右上角菜单选择“自定义仓库”。
4. 仓库地址填入：
   `https://github.com/demon3434/xiaodu_voice_control`
5. 类型选择 `Integration`。
6. 添加后搜索 `xiaodu_voice_control`。
7. 点击安装。
8. 安装完成后重启 Home Assistant。

### 方式 2：手动复制

把下面这个目录复制到 HA 配置目录下：

```text
custom_components/xiaodu_voice_control
```

例如：

```text
/config/custom_components/xiaodu_voice_control
```

然后重启 Home Assistant。

## 三、HA 配置

当前发布版仍需在 `configuration.yaml` 中添加一行 include：

```yaml
xiaodu_voice_control: !include xiaodu_voice_control.yaml
```

可参考：

- [examples/configuration.yaml.snippet](./examples/configuration.yaml.snippet)

然后在 HA 配置根目录创建 `xiaodu_voice_control.yaml`：

```yaml
service_url: http://127.0.0.1:8129
internal_api_token: replace_with_random_long_token
xiaodu_skill_id: replace_with_your_bot_id
xiaodu_client_secret: replace_with_client_secret
xiaodu_open_uids: []
```

示例文件：

- [examples/xiaodu_voice_control.yaml.example](./examples/xiaodu_voice_control.yaml.example)

字段说明：

- `service_url`
  - HA 集成访问独立服务容器的地址
  - 如果服务和 HA 在同一台主机，可用 `http://127.0.0.1:8129`
- `internal_api_token`
  - HA 集成与服务容器之间的内部鉴权令牌
  - 不是填给小度平台的
- `xiaodu_skill_id`
  - 小度技能 ID，也就是 `botID`
- `xiaodu_client_secret`
  - 小度技能平台里配置的 `ClientSecret`
- `xiaodu_open_uids`
  - 已捕获的授权用户 `openUid` 列表
  - 通常不需要手填，程序可自动获取

## 四、HA 页面中如何使用

安装并重启后，HA 侧边栏会出现：

- `小度语音设备`

页面支持：

- 新建设备
- 编辑设备
- 删除设备
- 按类型筛选
- 按名称关键字查询
- 按 HA 实体 ID 查询
- 配置服务参数
- 同步设备到独立服务

### 设备文件位置

HA 侧维护的设备主文件写在：

```text
/config/xiaodu_voice_control_devices.yaml
```

## 五、小度技能平台如何填写

在小度智能家居技能平台中，核心配置如下：

- 授权地址  
  `https://你的公网地址/xiaoduvc/auth/authorize`

- Token 地址  
  `https://你的公网地址/xiaoduvc/auth/token`

- WebService  
  `https://你的公网地址/xiaoduvc/service`

- `Client_Id`  
  `dueros`

- `ClientSecret`  
  与 HA 页面“配置服务”中填写的值保持一致

注意：

- 不要填 HA 原生的 `/auth/authorize`
- 不要把 `https://xiaodu.baidu.com` 当成 `Client_Id`
- 必须使用公网可访问的 `HTTPS` 地址

## 六、botID 和 openUid 从哪里获取

### botID

`botID` 就是小度技能 ID，可从以下位置获取：

- 小度技能平台“基础信息”页面
- 模拟测试请求报文中的 `debug.bot.id`

### openUid

小度平台通常不提供单独查看 `openUid` 的界面。推荐流程：

1. 在 HA 页面先保存服务配置。
2. 到小度技能平台重新授权。
3. 在模拟测试或真实设备中触发一次：
   - `发现设备`
   - 或真实控制/查询
4. 请求到达服务后，程序会自动记录当前账号对应的 `openUid`。
5. 回到 HA 的“配置服务”页面查看已捕获列表。

同一个技能可能被多个百度账号授权，所以这里设计成列表。

## 七、常见问题

### 1. 为什么小度 App 看不到新设备？

请依次检查：

1. HA 页面是否点击了“同步设备”
2. 小度技能是否重新授权
3. 服务容器日志中是否出现 `devicesync` 成功结果

### 2. 为什么语音没反应？

建议分开排查：

1. 看 HA 页面里设备是否存在
2. 看 discovery 是否已暴露这个设备
3. 再确认小度语义是否真正命中智能家居设备

对于温度、湿度类设备，建议命名成：

- `xx温度传感器`
- `xx湿度传感器`
- `xx温度计`

这样更容易被小度识别为智能家居查询，而不是天气类问句。

### 3. 为什么 `openUid` 是列表？

因为不同百度账号授权同一技能时，会生成不同的 `openUid`。

## 八、删除集成

当前版本删除 `xiaodu_voice_control` 时，建议按下面顺序操作，避免 Home Assistant 重启后侧边栏里仍然保留“`小度语音设备`”页面：

1. 在 Home Assistant 中进入“设置 -> 设备与服务”，找到 `XiaoDu Voice Control`，点击“删除”。
2. 打开 `configuration.yaml`，删除这一行：

```yaml
xiaodu_voice_control: !include xiaodu_voice_control.yaml
```

3. 如果你已经不再使用本集成，可一并删除下面两个文件：

```text
/config/xiaodu_voice_control.yaml
/config/xiaodu_voice_control_devices.yaml
```

4. 重启 Home Assistant。
5. 如果你同时也不再使用独立服务容器 `xiaodu_voice_control_service`，可再停止并删除该容器。

说明：

- 如果只在 HA 界面删除集成，但 `configuration.yaml` 中仍然保留了 `xiaodu_voice_control: !include xiaodu_voice_control.yaml`，组件在重启后仍可能继续加载。
- 后续版本会继续朝“仅通过集成界面安装/删除、不改 `configuration.yaml`”的方向收敛；当前发布版仍建议按以上步骤完整卸载。
