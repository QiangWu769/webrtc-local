# RTT测量时序图

## 四个时间戳的形成过程

```mermaid
sequenceDiagram
    participant C as 客户端(PC)
    participant N as 网络
    participant S as 服务器(Android)
    
    Note over C: T1: 客户端发送时间<br/>记录发送PING的时刻
    C->>C: T1 = get_current_time()<br/>(例: 1000.000秒)
    
    rect rgb(200, 230, 255)
        Note over C,N: 网络传输（上行）
        C->>N: PING消息<br/>[Type=0x01, T1=1000.000]
        N->>S: PING消息<br/>经过网络延迟(~2ms)
    end
    
    Note over S: T2: 服务器接收时间<br/>记录接收PING的时刻
    S->>S: T2 = get_current_time()<br/>(例: 2241.902秒)
    
    rect rgb(255, 230, 200)
        Note over S: 服务器处理
        S->>S: 解析PING消息<br/>准备PONG响应<br/>(处理时间~0.001ms)
    end
    
    Note over S: T3: 服务器发送时间<br/>记录发送PONG的时刻
    S->>S: T3 = get_current_time()<br/>(例: 2241.902秒)
    
    rect rgb(200, 230, 255)
        Note over S,N: 网络传输（下行）
        S->>N: PONG消息<br/>[Type=0x02, T1, T2, T3]
        N->>C: PONG消息<br/>经过网络延迟(~2ms)
    end
    
    Note over C: T4: 客户端接收时间<br/>记录接收PONG的时刻
    C->>C: T4 = get_current_time()<br/>(例: 1000.004秒)
    
    Note over C: 计算RTT和时钟偏移
    C->>C: RTT = (T4-T1) - (T3-T2)<br/>= (1000.004-1000.000) - (2241.902-2241.902)<br/>= 0.004 - 0.000 = 4ms
    
    C->>C: 网络延迟 = RTT/2 = 2ms
    
    C->>C: 时钟偏移 = T2 - T1 - 网络延迟<br/>= 2241.902 - 1000.000 - 0.002<br/>= 1241.900秒<br/>（服务器比客户端快1241.9秒）
```

## 时间线视图

```mermaid
gantt
    title RTT测量时间线
    dateFormat X
    axisFormat %L
    
    section 客户端
    发送PING (T1)           :milestone, c1, 0, 0
    接收PONG (T4)           :milestone, c4, 4, 0
    
    section 网络
    上行传输                :active, n1, 0, 2
    下行传输                :active, n2, 2, 2
    
    section 服务器  
    接收PING (T2)           :milestone, s2, 2, 0
    处理请求                :crit, sp, 2, 0
    发送PONG (T3)           :milestone, s3, 2, 0
```

## 计算公式详解

### 1. RTT（往返时延）
```
RTT = (T4 - T1) - (T3 - T2)
    = 总往返时间 - 服务器处理时间
    = 纯网络往返延迟
```

### 2. 时钟偏移
```
Clock_Offset = T2 - T1 - Network_Delay
其中: Network_Delay = RTT / 2 (假设对称)
```

### 3. 实际数值示例（来自您的测量）
- T1 = 1000.000 (客户端时间)
- T2 = 2241.902 (服务器时间，快1241秒)
- T3 = 2241.902 (几乎无处理延迟)
- T4 = 1000.004 (客户端时间)

计算结果：
- RTT = 4ms
- 时钟偏移 = +1241秒
- 网络单向延迟 ≈ 2ms

## 使用说明

1. 将此文件在支持Mermaid的Markdown编辑器中打开
2. 或访问 https://mermaid.live 并粘贴mermaid代码块内容
3. 或在GitHub上直接查看（GitHub原生支持Mermaid）