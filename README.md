# xiaodu_voice_control

`xiaodu_voice_control` 是一个 Home Assistant 自定义集成，用来把要暴露给小度的设备列表、技能参数和已捕获的 `openUid` 统一交给独立服务 `xiaodu_voice_control_service`，再由服务完成 OAuth、设备发现、控制和查询。

这个仓库适合通过 **HACS 自定义仓库** 安装集成。

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

## 安装顺序

建议严格按下面顺序操作：

1. 先部署独立服务 `xiaodu_voice_control_service`
2. 再通过 HACS 安装本集成
3. 重启 Home Assistant
4. 在 HA 侧边栏打开“**小度语音设备**”
5. 配置服务参数、添加设备、同步设备
6. 最后到小度技能平台配置并授权

## 一、先部署独立服务

这个集成依赖独立服务容器 `xiaodu_voice_control_service` 。

推荐直接使用 Docker Hub 镜像：

```bash
docker pull demon3434/xiaodu_voice_control_service:latest
```

独立服务的完整部署说明，请看：

- GitHub 代码仓库：[`https://github.com/demon3434/xiaodu_voice_control_service`](https://github.com/demon3434/xiaodu_voice_control_service)
- Docker Hub 镜像仓库：[`https://hub.docker.com/r/demon3434/xiaodu_voice_control_service`](https://hub.docker.com/r/demon3434/xiaodu_voice_control_service)

如果你已经把服务部署好了，并且浏览器可以打开：

- `http://你的服务地址:8129/`

就可以继续安装 HA 集成。

## 二、通过 HACS 安装本集成

### 方式 1：作为自定义仓库添加到 HACS

1. 打开 HACS
2. 进入“集成”
3. 右上角菜单选择“自定义存储库”
4. 仓库地址填入你的 GitHub 仓库地址
5. 类型选择 `Integration`
6. 添加后搜索 `xiaodu_voice_control`
7. 点击安装
8. 安装完成后重启 Home Assistant

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

本集成只增加一个 include，不把大量配置直接堆进 `configuration.yaml`。

把下面这行加入 `configuration.yaml`：

```yaml
xiaodu_voice_control: !include xiaodu_voice_control.yaml
```

你也可以直接参考：

- [examples/configuration.yaml.snippet](https://github.com/demon3434/xiaodu_voice_control/blob/main/examples/xiaodu_voice_control.yaml.example)

然后在 HA 配置根目录创建 `xiaodu_voice_control.yaml` ：

```yaml
service_url: http://127.0.0.1:8129
internal_api_token: replace_with_random_long_token
xiaodu_skill_id: replace_with_your_bot_id
xiaodu_client_secret: replace_with_client_secret
xiaodu_open_uids: []
```

示例文件见：

- [examples/xiaodu_voice_control.yaml.example](https://github.com/demon3434/xiaodu_voice_control/blob/main/examples/xiaodu_voice_control.yaml.example)

说明：

- `service_url`
  HA 集成访问独立服务 `xiaodu_voice_control_service` 的地址。如果与 HA 部署在同一台主机，可以写成 `http://127.0.0.1:8129`
- `internal_api_token`
  HA 集成和独立服务之间的内部鉴权令牌，不是填给小度平台的
- `xiaodu_skill_id`
  小度技能 ID，也就是 botID
- `xiaodu_client_secret`
  小度技能平台里配置的 `ClientSecret`
- `xiaodu_open_uids`
  已捕获到的授权用户 `openUid` 列表。通常不需要手填，程序会自动记录

## 四、HA 页面里做什么

安装并重启后，HA 侧边栏会出现：

- `小度语音设备`

这个页面支持：

- 新建设备
- 编辑设备
- 删除设备
- 按类型/名称/实体 ID 筛选
- 分页显示设备
- 配置服务参数
- 同步设备到独立服务
- 触发小度云端设备同步

### 设备文件

设备主文件写在 HA 根目录：

```text
/config/xiaodu_voice_control_devices.yaml
```

HA 页面维护的是这份主文件，服务容器只保存运行副本。

## 五、小度技能平台配置

在小度智能家居技能平台中，核心字段这样填写：

- 授权地址  
  `https://你的公网地址/xiaoduvc/auth/authorize`

- Token 地址  
  `https://你的公网地址/xiaoduvc/auth/token`

- WebService  
  `https://你的公网地址/xiaoduvc/service`

- `Client_Id`  
  `dueros`

- `ClientSecret`  
  与 HA 页面“配置服务”里填写的值保持一致

注意：

- 不要填 HA 原生的 `/auth/authorize`
- 不要把 `https://xiaodu.baidu.com` 当成 `Client_Id`
- 需要使用公网可访问的 HTTPS 地址

## 六、botID 和 openUid 从哪里来

### botID

也就是小度技能 ID。可以从以下位置获取：

- 小度技能平台“基础信息”页面
- 模拟测试请求报文里的 `debug.bot.id`

### openUid

小度平台通常不会提供一个单独的“查看 openUid”页面。

正确方式是：

1. 在小度技能平台完成授权
2. 在小度 App 或模拟测试里触发一次：
   - 发现设备
   - 或真实控制
3. 请求到达服务后，程序自动捕获 `openUid`
4. 回到 HA 的“配置服务”页面查看已捕获列表

因为同一个技能可能被多个用户授权，所以这里设计成列表。

## 七、常见问题

### 1. 为什么小度 App 看不到新设备？

先检查：

1. HA 页面是否点了“同步设备”
2. 小度技能是否重新授权
3. 服务容器日志里是否有 `devicesync` 成功

### 2. 为什么语音没反应？

先分开排查：

1. 看 HA 页面里这个设备是否已经存在
2. 看服务 discovery 是否已经暴露这个设备
3. 再看小度语义是否真的命中了智能家居设备

对于温度、湿度类设备，建议命名成：

- `xx温度传感器`
- `xx湿度传感器`
- `xx温度计`

避免被小度误路由到天气类技能。

### 3. `openUid` 为什么是列表？

因为多个百度账号授权同一个技能时，会生成不同的 `openUid`。

## 八、仓库用途说明

这个仓库主要提供：

- 可通过 HACS 安装的 Home Assistant 集成
- 面向集成用户的配置说明
