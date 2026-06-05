package com.minecraftbc.core;

import net.minecraft.resources.ResourceLocation;
import org.apache.logging.log4j.Logger;

import java.nio.file.Path;
import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * 平台抽象层
 * 
 * 定义MinecraftBC与具体加载器（Fabric/Forge/NeoForge）交互的接口。
 * 每个加载器需要实现此接口。
 */
public interface Platform {
    
    /**
     * 获取加载器名称
     */
    String getPlatformName();
    
    /**
     * 获取Minecraft版本
     */
    String getMinecraftVersion();
    
    /**
     * 获取配置目录
     */
    Path getConfigDir();
    
    /**
     * 获取日志记录器
     */
    Logger getLogger();
    
    /**
     * 检查当前环境是否是客户端
     */
    boolean isClient();
    
    /**
     * 检查当前环境是否是服务器
     */
    boolean isServer();
    
    /**
     * 在客户端线程上执行
     */
    void executeOnClient(Runnable task);
    
    /**
     * 在服务器线程上执行
     */
    void executeOnServer(Runnable task);
    
    /**
     * 注册网络通道
     * 
     * @param channelId 通道ID
     * @param handler 包处理器
     */
    <T> void registerChannel(ResourceLocation channelId, Class<T> packetClass, PacketSerializer<T> serializer, PacketHandler<T> handler);
    
    /**
     * 发送包到服务器
     */
    <T> void sendToServer(T packet);
    
    /**
     * 发送包到特定客户端
     */
    <T> void sendToPlayer(Object player, T packet);
    
    /**
     * 注册客户端 tick 回调
     */
    void registerClientTick(Runnable callback);
    
    /**
     * 注册服务器 tick 回调
     */
    void registerServerTick(Runnable callback);
    
    /**
     * 注册服务器列表渲染回调
     */
    void registerServerListRender(Consumer<Object> callback);
    
    /**
     * 获取当前玩家的UUID（客户端）
     */
    String getClientPlayerUUID();
    
    /**
     * 获取当前玩家名称（客户端）
     */
    String getClientPlayerName();
    
    /**
     * 是否为开发环境
     */
    boolean isDevelopmentEnvironment();
    
    /**
     * 包序列化接口
     */
    interface PacketSerializer<T> {
        T read(Object byteBuf);
        void write(Object byteBuf, T packet);
    }
    
    /**
     * 包处理接口
     */
    interface PacketHandler<T> {
        void handle(T packet, PacketContext context);
    }
    
    /**
     * 包上下文
     */
    interface PacketContext {
        Object getPlayer(); // 发送者
        boolean isClientSide();
        void execute(Runnable task);
    }
}
