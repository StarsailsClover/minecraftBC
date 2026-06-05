package com.minecraftbc.core;

import com.minecraftbc.config.MinecraftBCConfig;
import com.minecraftbc.external.ExternalClientManager;
import com.minecraftbc.network.P2PNetworkManager;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * MinecraftBC 核心入口
 * 
 * 跨加载器共享的核心逻辑，不依赖任何特定加载器的API。
 * 通过 Platform 抽象层与具体加载器交互。
 */
public class MinecraftBC {
    public static final String MOD_ID = "minecraftbc";
    public static final String MOD_NAME = "MinecraftBC";
    public static final String MOD_VERSION = "2.0.0";
    
    private static final Logger LOGGER = LogManager.getLogger(MOD_ID);
    
    private static MinecraftBC INSTANCE;
    
    private final Platform platform;
    private final MinecraftBCConfig config;
    private final ExternalClientManager externalClient;
    private final P2PNetworkManager networkManager;
    
    private boolean initialized = false;
    
    private MinecraftBC(Platform platform) {
        this.platform = platform;
        this.config = new MinecraftBCConfig(platform.getConfigDir());
        this.externalClient = new ExternalClientManager(this);
        this.networkManager = new P2PNetworkManager(this);
    }
    
    /**
     * 初始化核心（由加载器特定代码调用）
     */
    public static void init(Platform platform) {
        if (INSTANCE != null) {
            throw new IllegalStateException("MinecraftBC already initialized");
        }
        INSTANCE = new MinecraftBC(platform);
        INSTANCE.onInitialize();
    }
    
    /**
     * 获取实例
     */
    public static MinecraftBC getInstance() {
        if (INSTANCE == null) {
            throw new IllegalStateException("MinecraftBC not initialized");
        }
        return INSTANCE;
    }
    
    private void onInitialize() {
        LOGGER.info("Initializing {} v{} on {}", MOD_NAME, MOD_VERSION, platform.getPlatformName());
        
        // 加载配置
        config.load();
        
        // 初始化网络管理器
        networkManager.initialize();
        
        // 连接到外部客户端
        if (config.isExternalClientEnabled()) {
            externalClient.connect(config.getExternalClientHost(), config.getExternalClientPort());
        }
        
        initialized = true;
        LOGGER.info("{} initialization complete", MOD_NAME);
    }
    
    /**
     * 客户端初始化完成后的回调
     */
    public void onClientReady() {
        LOGGER.info("Client ready, registering server list hooks");
        networkManager.registerServerListHook();
    }
    
    /**
     * 关闭时的清理
     */
    public void onShutdown() {
        LOGGER.info("Shutting down {}" , MOD_NAME);
        externalClient.disconnect();
        networkManager.shutdown();
        config.save();
    }
    
    // Getters
    public Platform getPlatform() { return platform; }
    public MinecraftBCConfig getConfig() { return config; }
    public ExternalClientManager getExternalClient() { return externalClient; }
    public P2PNetworkManager getNetworkManager() { return networkManager; }
    public Logger getLogger() { return LOGGER; }
    public boolean isInitialized() { return initialized; }
}
