package com.minecraftbc.neoforge;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.core.Platform;
import net.minecraft.client.Minecraft;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLClientSetupEvent;
import net.neoforged.fml.loading.FMLLoader;
import net.neoforged.fml.loading.FMLPaths;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.server.ServerStartingEvent;
import net.neoforged.neoforge.event.server.ServerStoppingEvent;
import net.neoforged.neoforge.event.tick.ClientTickEvent;
import net.neoforged.neoforge.event.tick.ServerTickEvent;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlerEvent;
import net.neoforged.neoforge.network.handling.IPayloadContext;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.nio.file.Path;
import java.util.function.Consumer;

/**
 * NeoForge 平台实现
 */
@Mod("minecraftbc")
public class MinecraftBCNeoForge implements Platform {
    
    private static final Logger LOGGER = LogManager.getLogger("MinecraftBC-NeoForge");
    
    private final IEventBus modEventBus;
    private final IEventBus gameEventBus;
    
    public MinecraftBCNeoForge(IEventBus modEventBus, ModContainer modContainer) {
        this.modEventBus = modEventBus;
        this.gameEventBus = NeoForge.EVENT_BUS;
        
        LOGGER.info("MinecraftBC NeoForge initializing...");
        
        // 注册事件
        modEventBus.addListener(this::onClientSetup);
        modEventBus.addListener(this::onRegisterPayloadHandlers);
        
        gameEventBus.addListener(this::onServerStarting);
        gameEventBus.addListener(this::onServerStopping);
        gameEventBus.addListener(this::onClientTick);
        gameEventBus.addListener(this::onServerTick);
        gameEventBus.addListener(this::onPlayerLoggedIn);
    }
    
    private void onClientSetup(FMLClientSetupEvent event) {
        LOGGER.info("MinecraftBC NeoForge client setup");
        
        event.enqueueWork(() -> {
            // 初始化核心
            MinecraftBC.init(this);
            
            // 客户端就绪
            Minecraft.getInstance().execute(() -> {
                MinecraftBC.getInstance().onClientReady();
            });
        });
    }
    
    private void onServerStarting(ServerStartingEvent event) {
        LOGGER.info("Server starting: {}", event.getServer().getServerModName());
    }
    
    private void onServerStopping(ServerStoppingEvent event) {
        if (MinecraftBC.getInstance() != null) {
            MinecraftBC.getInstance().onShutdown();
        }
    }
    
    private void onClientTick(ClientTickEvent.Pre event) {
        // 客户端tick
    }
    
    private void onServerTick(ServerTickEvent.Pre event) {
        // 服务器tick
    }
    
    private void onPlayerLoggedIn(PlayerEvent.PlayerLoggedInEvent event) {
        LOGGER.info("Player logged in: {}", event.getEntity().getName().getString());
    }
    
    private void onRegisterPayloadHandlers(RegisterPayloadHandlerEvent event) {
        // 注册网络处理器
        LOGGER.info("Registering payload handlers");
    }
    
    // Platform Implementation
    
    @Override
    public String getPlatformName() {
        return "NeoForge";
    }
    
    @Override
    public String getMinecraftVersion() {
        return FMLLoader.versionInfo().mcVersion();
    }
    
    @Override
    public Path getConfigDir() {
        return FMLPaths.CONFIGDIR.get();
    }
    
    @Override
    public Logger getLogger() {
        return LOGGER;
    }
    
    @Override
    public boolean isClient() {
        return FMLLoader.getDist() == Dist.CLIENT;
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
        // NeoForge需要服务器实例
        MinecraftServer server = Minecraft.getInstance().getSingleplayerServer();
        if (server != null) {
            server.execute(task);
        }
    }
    
    @Override
    public <T> void registerChannel(ResourceLocation channelId, Class<T> packetClass, PacketSerializer<T> serializer, PacketHandler<T> handler) {
        // NeoForge使用Modern Networking API
        // 需要在onRegisterPayloadHandlers中注册
    }
    
    @Override
    public <T> void sendToServer(T packet) {
        // 使用PacketDistributor
        PacketDistributor.SERVER.noArg().send(packet);
    }
    
    @Override
    public <T> void sendToPlayer(Object player, T packet) {
        if (player instanceof ServerPlayer serverPlayer) {
            PacketDistributor.PLAYER.with(serverPlayer).send(packet);
        }
    }
    
    @Override
    public void registerClientTick(Runnable callback) {
        gameEventBus.addListener((ClientTickEvent.Pre event) -> callback.run());
    }
    
    @Override
    public void registerServerTick(Runnable callback) {
        gameEventBus.addListener((ServerTickEvent.Pre event) -> callback.run());
    }
    
    @Override
    public void registerServerListRender(Consumer<Object> callback) {
        // NeoForge需要mixin或事件来修改服务器列表
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
        return !FMLLoader.isProduction();
    }
    
    // 服务器列表渲染回调
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
