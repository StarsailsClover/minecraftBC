package com.minecraftbc.network;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.network.packet.P2PServerInfo;
import org.apache.logging.log4j.Logger;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;

/**
 * P2P 网络管理器
 * 
 * 管理P2P服务器列表，处理连接请求。
 */
public class P2PNetworkManager {
    
    private final MinecraftBC mod;
    private final Logger logger;
    
    private final Map<String, P2PServerInfo> serverList = new ConcurrentHashMap<>();
    private final List<Consumer<List<P2PServerInfo>>> serverListListeners = new ArrayList<>();
    
    private boolean initialized = false;
    
    public P2PNetworkManager(MinecraftBC mod) {
        this.mod = mod;
        this.logger = mod.getLogger();
    }
    
    /**
     * 初始化
     */
    public void initialize() {
        if (initialized) {
            return;
        }
        
        logger.info("Initializing P2P Network Manager");
        
        // 设置外部客户端的回调
        mod.getExternalClient().setServerListCallback(this::onServerListReceived);
        
        initialized = true;
    }
    
    /**
     * 注册服务器列表UI钩子
     */
    public void registerServerListHook() {
        // 由平台特定代码调用，在多人游戏菜单中注入P2P服务器列表
        logger.info("Registering server list hooks");
        
        // 当收到服务器列表时，通知UI
        addServerListListener(servers -> {
            mod.getPlatform().executeOnClient(() -> {
                // 平台特定代码会处理UI更新
                updateServerListUI(servers);
            });
        });
    }
    
    /**
     * 连接到P2P服务器
     */
    public void connectToServer(P2PServerInfo server) {
        logger.info("Connecting to P2P server: {} ({})", server.name, server.id);
        
        // 请求外部客户端建立P2P连接
        mod.getExternalClient().requestConnect(server.id, server.host, server.port);
    }
    
    /**
     * 当P2P连接就绪时调用
     */
    public void onP2PConnectionReady(String serverId, String localHost, int localPort) {
        logger.info("P2P connection ready for {} at {}:{}", serverId, localHost, localPort);
        
        // 通知游戏连接到本地代理端口
        mod.getPlatform().executeOnClient(() -> {
            // 平台特定代码：修改连接目标为本地代理
            redirectConnection(serverId, localHost, localPort);
        });
    }
    
    /**
     * 获取服务器列表
     */
    public List<P2PServerInfo> getServerList() {
        return Collections.unmodifiableList(new ArrayList<>(serverList.values()));
    }
    
    /**
     * 添加服务器列表监听器
     */
    public void addServerListListener(Consumer<List<P2PServerInfo>> listener) {
        serverListListeners.add(listener);
    }
    
    /**
     * 当收到服务器列表时
     */
    private void onServerListReceived(List<P2PServerInfo> servers) {
        logger.debug("Received {} P2P servers", servers.size());
        
        // 更新本地列表
        serverList.clear();
        for (P2PServerInfo server : servers) {
            serverList.put(server.id, server);
        }
        
        // 通知监听器
        for (Consumer<List<P2PServerInfo>> listener : serverListListeners) {
            try {
                listener.accept(servers);
            } catch (Exception e) {
                logger.error("Error in server list listener: {}", e.getMessage());
            }
        }
    }
    
    /**
     * 更新服务器列表UI（平台特定实现）
     */
    private void updateServerListUI(List<P2PServerInfo> servers) {
        // 由Architectury的平台特定代码实现
        // 在多人游戏菜单中插入P2P服务器
    }
    
    /**
     * 重定向连接（平台特定实现）
     */
    private void redirectConnection(String serverId, String localHost, int localPort) {
        // 由Architectury的平台特定代码实现
        // 修改ConnectScreen的连接目标
    }
    
    /**
     * 关闭
     */
    public void shutdown() {
        logger.info("Shutting down P2P Network Manager");
        serverList.clear();
        serverListListeners.clear();
    }
}
