package com.minecraftbc.config;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * MinecraftBC 配置管理
 * 
 * 管理模组与外部客户端的配置参数。
 */
public class MinecraftBCConfig {
    
    private static final Logger LOGGER = LogManager.getLogger("MinecraftBC");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final String CONFIG_FILE = "minecraftbc.json";
    
    private final Path configPath;
    private ConfigData data;
    
    public MinecraftBCConfig(Path configDir) {
        this.configPath = configDir.resolve(CONFIG_FILE);
        this.data = new ConfigData();
    }
    
    /**
     * 加载配置
     */
    public void load() {
        if (Files.exists(configPath)) {
            try {
                String json = Files.readString(configPath);
                data = GSON.fromJson(json, ConfigData.class);
                LOGGER.info("Loaded config from {}", configPath);
            } catch (IOException e) {
                LOGGER.error("Failed to load config: {}", e.getMessage());
                data = new ConfigData();
            }
        } else {
            LOGGER.info("Config not found, using defaults");
            save();
        }
    }
    
    /**
     * 保存配置
     */
    public void save() {
        try {
            Files.createDirectories(configPath.getParent());
            String json = GSON.toJson(data);
            Files.writeString(configPath, json);
            LOGGER.debug("Saved config to {}", configPath);
        } catch (IOException e) {
            LOGGER.error("Failed to save config: {}", e.getMessage());
        }
    }
    
    // Getters
    public boolean isExternalClientEnabled() { return data.externalClientEnabled; }
    public String getExternalClientHost() { return data.externalClientHost; }
    public int getExternalClientPort() { return data.externalClientPort; }
    public int getModVersion() { return data.modVersion; }
    public boolean isAutoReconnect() { return data.autoReconnect; }
    public boolean isDebugMode() { return data.debugMode; }
    public String getPreferredProtocol() { return data.preferredProtocol; }
    
    // Setters
    public void setExternalClientEnabled(boolean enabled) { data.externalClientEnabled = enabled; }
    public void setExternalClientHost(String host) { data.externalClientHost = host; }
    public void setExternalClientPort(int port) { data.externalClientPort = port; }
    public void setDebugMode(boolean debug) { data.debugMode = debug; }
    
    /**
     * 配置数据结构
     */
    private static class ConfigData {
        boolean externalClientEnabled = true;
        String externalClientHost = "127.0.0.1";
        int externalClientPort = 25566;
        int modVersion = 2;
        boolean autoReconnect = true;
        boolean debugMode = false;
        String preferredProtocol = "fastlink"; // fastlink, webrtc, auto
    }
}
