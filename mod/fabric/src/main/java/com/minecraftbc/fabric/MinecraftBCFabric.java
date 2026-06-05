package com.minecraftbc.fabric;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.core.Platform;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.PacketByteBufs;
import net.fabricmc.fabric.api.networking.v1.PacketSender;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.loader.api.ModContainer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.nio.file.Path;
import java.util.function.Consumer;
import java.util.function.Supplier;

/**
 * Fabric 平台实现
 */
public class MinecraftBCFabric implements ModInitializer, ClientModInitializer, Platform {
    
    private static final Logger LOGGER = LogManager.getLogger("MinecraftBC-Fabric");
    private static MinecraftBCFabric INSTANCE;
    
    public MinecraftBCFabric() {
        INSTANCE = this;
    }
    
    @Override
    public void onInitialize() {
        LOGGER.info("MinecraftBC Fabric initializing...");
        
        // 注册服务器tick
        ServerTickEvents.START_SERVER_TICK.register(this::onServerTick);
    }
    
    @Override
    public void onInitializeClient() {
        LOGGER.info("MinecraftBC Fabric client initializing...");
        
        // 初始化核心
        MinecraftBC.init(this);
        
        // 注册客户端tick
        ClientTickEvents.START_CLIENT_TICK.register(this::onClientTick);
        
        // 注册客户端停止事件
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> {
            MinecraftBC.getInstance().onShutdown();
        });
        
        // 客户端就绪
        Minecraft.getInstance().execute(() -> {
            MinecraftBC.getInstance().onClientReady();
        });
    }
    
    private void onClientTick(Minecraft client) {
        // 每tick调用
    }
    
    private void onServerTick(MinecraftServer server) {
        // 服务器tick
    }
    
    // Platform Implementation
    
    @Override
    public String getPlatformName() {
        return "Fabric";
    }
    
    @Override
    public String getMinecraftVersion() {
        return FabricLoader.getInstance().getModContainer("minecraft")
            .map(ModContainer::getMetadata)
            .map(metadata -> metadata.getVersion().getFriendlyString())
            .orElse("unknown");
    }
    
    @Override
    public Path getConfigDir() {
        return FabricLoader.getInstance().getConfigDir();
    }
    
    @Override
    public Logger getLogger() {
        return LOGGER;
    }
    
    @Override
    public boolean isClient() {
        return FabricLoader.getInstance().getEnvironmentType() == net.fabricmc.api.EnvType.CLIENT;
    }
    
    @Override
    public boolean isServer() {
        return !isClient();
    }
    
    @Override
    public void executeOnClient(Runnable task) {
        Minecraft.getInstance().execute(task);
    }
    
    @Override
    public void executeOnServer(Runnable task) {
        // Fabric没有直接获取服务器实例的方法
        LOGGER.warn("executeOnServer called but not implemented");
    }
    
    @Override
    public <T> void registerChannel(ResourceLocation channelId, Class<T> packetClass, PacketSerializer<T> serializer, PacketHandler<T> handler) {
        // Fabric网络注册
        ClientPlayNetworking.registerGlobalReceiver(channelId, (client, listener, buf, responseSender) -> {
            T packet = serializer.read(buf);
            client.execute(() -> handler.handle(packet, new FabricPacketContext(listener, true)));
        });
        
        ServerPlayNetworking.registerGlobalReceiver(channelId, (server, player, listener, buf, responseSender) -> {
            T packet = serializer.read(buf);
            server.execute(() -> handler.handle(packet, new FabricPacketContext(player, false)));
        });
    }
    
    @Override
    public <T> void sendToServer(T packet) {
        // 通过Fabric网络发送
        // 需要预先注册的发送器
    }
    
    @Override
    public <T> void sendToPlayer(Object player, T packet) {
        // 发送给特定玩家
    }
    
    @Override
    public void registerClientTick(Runnable callback) {
        ClientTickEvents.START_CLIENT_TICK.register(client -> callback.run());
    }
    
    @Override
    public void registerServerTick(Runnable callback) {
        ServerTickEvents.START_SERVER_TICK.register(server -> callback.run());
    }
    
    @Override
    public void registerServerListRender(Consumer<Object> callback) {
        // Fabric需要mixin来修改服务器列表UI
        // 这里注册回调，由mixin调用
        ServerListRenderer.registerCallback(callback);
    }
    
    @Override
    public String getClientPlayerUUID() {
        LocalPlayer player = Minecraft.getInstance().player;
        return player != null ? player.getUUID().toString() : "unknown";
    }
    
    @Override
    public String getClientPlayerName() {
        LocalPlayer player = Minecraft.getInstance().player;
        return player != null ? player.getName().getString() : "unknown";
    }
    
    @Override
    public boolean isDevelopmentEnvironment() {
        return FabricLoader.getInstance().isDevelopmentEnvironment();
    }
    
    // 内部类
    
    private class FabricPacketContext implements PacketContext {
        private final Object player;
        private final boolean clientSide;
        
        FabricPacketContext(Object player, boolean clientSide) {
            this.player = player;
            this.clientSide = clientSide;
        }
        
        @Override
        public Object getPlayer() {
            return player;
        }
        
        @Override
        public boolean isClientSide() {
            return clientSide;
        }
        
        @Override
        public void execute(Runnable task) {
            if (clientSide) {
                Minecraft.getInstance().execute(task);
            }
        }
    }
    
    // 服务器列表渲染回调注册
    public static class ServerListRenderer {
        private static Consumer<Object> callback;
        
        public static void registerCallback(Consumer<Object> cb) {
            callback = cb;
        }
        
        public static Consumer<Object> getCallback() {
            return callback;
        }
    }
}
