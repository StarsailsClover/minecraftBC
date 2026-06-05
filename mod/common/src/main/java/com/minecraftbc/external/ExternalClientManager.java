package com.minecraftbc.external;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.network.packet.P2PServerInfo;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import org.apache.logging.log4j.Logger;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.*;
import java.util.function.Consumer;

/**
 * 外部客户端连接管理器
 * 
 * 负责与Python外部客户端建立TCP连接，并管理双向通信。
 * 
 * 协议设计：
 * [Length: 4字节] [Packet Type: 1字节] [Payload: N字节]
 * 
 * 包类型：
 * 0x01: HEARTBEAT - 心跳
 * 0x02: HANDSHAKE - 握手
 * 0x03: SERVER_LIST - 服务器列表更新
 * 0x04: CONNECT_REQUEST - 连接请求
 * 0x05: CONNECT_RESPONSE - 连接响应
 * 0x06: DISCONNECT - 断开连接
 * 0x07: ERROR - 错误
 * 0x08: AUTH - 认证
 */
public class ExternalClientManager {
    
    private static final int PROTOCOL_VERSION = 1;
    private static final long HEARTBEAT_INTERVAL_MS = 5000;
    private static final long RECONNECT_DELAY_MS = 3000;
    
    private final MinecraftBC mod;
    private final Logger logger;
    
    private volatile Socket socket;
    private volatile DataOutputStream output;
    private volatile DataInputStream input;
    
    private final ScheduledExecutorService executor;
    private final ExecutorService callbackExecutor;
    
    private volatile boolean connected = false;
    private volatile boolean shouldReconnect = true;
    
    private Consumer<List<P2PServerInfo>> serverListCallback;
    private Consumer<ConnectionStatus> statusCallback;
    
    public ExternalClientManager(MinecraftBC mod) {
        this.mod = mod;
        this.logger = mod.getLogger();
        this.executor = Executors.newScheduledThreadPool(2);
        this.callbackExecutor = Executors.newSingleThreadExecutor();
    }
    
    /**
     * 连接到外部客户端
     */
    public void connect(String host, int port) {
        executor.submit(() -> connectInternal(host, port));
    }
    
    private void connectInternal(String host, int port) {
        while (shouldReconnect && !connected) {
            try {
                logger.info("Connecting to external client at {}:{}", host, port);
                
                socket = new Socket(host, port);
                socket.setTcpNoDelay(true);
                socket.setKeepAlive(true);
                
                output = new DataOutputStream(socket.getOutputStream());
                input = new DataInputStream(socket.getInputStream());
                
                // 发送握手
                sendHandshake();
                
                connected = true;
                logger.info("Connected to external client");
                
                if (statusCallback != null) {
                    callbackExecutor.execute(() -> statusCallback.accept(ConnectionStatus.CONNECTED));
                }
                
                // 启动心跳
                startHeartbeat();
                
                // 开始读取循环
                readLoop();
                
            } catch (IOException e) {
                logger.error("Failed to connect to external client: {}", e.getMessage());
                connected = false;
                
                if (statusCallback != null) {
                    callbackExecutor.execute(() -> statusCallback.accept(ConnectionStatus.DISCONNECTED));
                }
                
                // 等待后重连
                try {
                    Thread.sleep(RECONNECT_DELAY_MS);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
    }
    
    /**
     * 发送握手包
     */
    private void sendHandshake() throws IOException {
        ByteBuf buf = Unpooled.buffer();
        buf.writeInt(PROTOCOL_VERSION);  // 协议版本
        buf.writeInt(mod.getConfig().getModVersion());
        writeString(buf, mod.getPlatform().getMinecraftVersion());
        writeString(buf, mod.getPlatform().getClientPlayerUUID());
        writeString(buf, mod.getPlatform().getClientPlayerName());
        
        sendPacket(PacketType.HANDSHAKE, buf);
    }
    
    /**
     * 请求连接服务器
     */
    public void requestConnect(String serverId, String host, int port) {
        if (!connected) {
            logger.error("Cannot request connection: not connected to external client");
            return;
        }
        
        ByteBuf buf = Unpooled.buffer();
        writeString(buf, serverId);
        writeString(buf, host);
        buf.writeInt(port);
        
        try {
            sendPacket(PacketType.CONNECT_REQUEST, buf);
        } catch (IOException e) {
            logger.error("Failed to send connect request: {}", e.getMessage());
        }
    }
    
    /**
     * 发送数据包
     */
    private void sendPacket(PacketType type, ByteBuf payload) throws IOException {
        if (!connected || output == null) {
            throw new IOException("Not connected");
        }
        
        synchronized (output) {
            // 总长度（不含自身）
            int totalLength = 1 + payload.readableBytes(); // type + payload
            output.writeInt(totalLength);
            output.writeByte(type.getId());
            output.write(payload.array(), payload.readerIndex(), payload.readableBytes());
            output.flush();
        }
    }
    
    /**
     * 读取循环
     */
    private void readLoop() {
        while (connected && socket != null && !socket.isClosed()) {
            try {
                int length = input.readInt();
                if (length > 65536) {
                    logger.error("Packet too large: {}", length);
                    disconnect();
                    break;
                }
                
                byte type = input.readByte();
                byte[] payload = new byte[length - 1];
                input.readFully(payload);
                
                ByteBuf buf = Unpooled.wrappedBuffer(payload);
                handlePacket(PacketType.fromId(type), buf);
                
            } catch (IOException e) {
                if (connected) {
                    logger.error("Read error: {}", e.getMessage());
                    disconnect();
                }
                break;
            }
        }
    }
    
    /**
     * 处理收到的包
     */
    private void handlePacket(PacketType type, ByteBuf buf) {
        switch (type) {
            case HEARTBEAT:
                // 心跳响应，无需处理
                break;
                
            case SERVER_LIST:
                handleServerList(buf);
                break;
                
            case CONNECT_RESPONSE:
                handleConnectResponse(buf);
                break;
                
            case ERROR:
                String error = readString(buf);
                logger.error("External client error: {}", error);
                break;
                
            default:
                logger.warn("Unknown packet type: {}", type);
        }
    }
    
    /**
     * 处理服务器列表
     */
    private void handleServerList(ByteBuf buf) {
        int count = buf.readInt();
        List<P2PServerInfo> servers = new java.util.ArrayList<>(count);
        
        for (int i = 0; i < count; i++) {
            P2PServerInfo info = new P2PServerInfo();
            info.id = readString(buf);
            info.name = readString(buf);
            info.description = readString(buf);
            info.host = readString(buf);
            info.port = buf.readInt();
            info.latency = buf.readInt();
            info.playerCount = buf.readInt();
            info.maxPlayers = buf.readInt();
            info.version = readString(buf);
            servers.add(info);
        }
        
        logger.debug("Received {} servers from external client", count);
        
        if (serverListCallback != null) {
            final List<P2PServerInfo> finalServers = servers;
            callbackExecutor.execute(() -> serverListCallback.accept(finalServers));
        }
    }
    
    /**
     * 处理连接响应
     */
    private void handleConnectResponse(ByteBuf buf) {
        boolean success = buf.readBoolean();
        String serverId = readString(buf);
        String localHost = readString(buf);
        int localPort = buf.readInt();
        String message = readString(buf);
        
        if (success) {
            logger.info("Connection to {} established at {}:{}", serverId, localHost, localPort);
            // 通知游戏连接到本地代理端口
            mod.getNetworkManager().onP2PConnectionReady(serverId, localHost, localPort);
        } else {
            logger.error("Failed to connect to {}: {}", serverId, message);
        }
    }
    
    /**
     * 启动心跳
     */
    private void startHeartbeat() {
        executor.scheduleAtFixedRate(() -> {
            if (connected && output != null) {
                try {
                    ByteBuf buf = Unpooled.buffer(0);
                    sendPacket(PacketType.HEARTBEAT, buf);
                } catch (IOException e) {
                    logger.error("Heartbeat failed: {}", e.getMessage());
                    disconnect();
                }
            }
        }, HEARTBEAT_INTERVAL_MS, HEARTBEAT_INTERVAL_MS, TimeUnit.MILLISECONDS);
    }
    
    /**
     * 断开连接
     */
    public void disconnect() {
        shouldReconnect = false;
        connected = false;
        
        try {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
        } catch (IOException ignored) {}
        
        logger.info("Disconnected from external client");
        
        if (statusCallback != null) {
            callbackExecutor.execute(() -> statusCallback.accept(ConnectionStatus.DISCONNECTED));
        }
    }
    
    /**
     * 设置服务器列表回调
     */
    public void setServerListCallback(Consumer<List<P2PServerInfo>> callback) {
        this.serverListCallback = callback;
    }
    
    /**
     * 设置状态回调
     */
    public void setStatusCallback(Consumer<ConnectionStatus> callback) {
        this.statusCallback = callback;
    }
    
    /**
     * 是否已连接
     */
    public boolean isConnected() {
        return connected;
    }
    
    // 工具方法
    private String readString(ByteBuf buf) {
        int len = buf.readInt();
        byte[] bytes = new byte[len];
        buf.readBytes(bytes);
        return new String(bytes, StandardCharsets.UTF_8);
    }
    
    private void writeString(ByteBuf buf, String str) {
        byte[] bytes = str.getBytes(StandardCharsets.UTF_8);
        buf.writeInt(bytes.length);
        buf.writeBytes(bytes);
    }
    
    // 枚举和类
    public enum PacketType {
        HEARTBEAT(0x01),
        HANDSHAKE(0x02),
        SERVER_LIST(0x03),
        CONNECT_REQUEST(0x04),
        CONNECT_RESPONSE(0x05),
        DISCONNECT(0x06),
        ERROR(0x07),
        AUTH(0x08);
        
        private final int id;
        
        PacketType(int id) {
            this.id = id;
        }
        
        public int getId() {
            return id;
        }
        
        public static PacketType fromId(int id) {
            for (PacketType type : values()) {
                if (type.id == id) {
                    return type;
                }
            }
            return null;
        }
    }
    
    public enum ConnectionStatus {
        CONNECTED,
        DISCONNECTED,
        CONNECTING,
        ERROR
    }
}
