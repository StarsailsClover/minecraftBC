package com.minecraftbc.mixin.core;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.network.packet.P2PServerInfo;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.multiplayer.ServerSelectionList;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.ServerList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.List;

/**
 * ServerSelectionList Mixin
 * 
 * 在多人游戏服务器列表中注入P2P服务器项。
 * 
 * 实现方式：
 * 1. 监听服务器列表更新
 * 2. 从外部客户端获取P2P服务器列表
 * 3. 将P2P服务器添加到列表顶部或特定分类
 * 4. 标记这些服务器以便渲染时特殊显示
 */
@Mixin(ServerSelectionList.class)
public class MixinServerSelectionList {
    
    @Unique
    private JoinMultiplayerScreen minecraftbc$parentScreen;
    
    /**
     * 注入构造函数以保存父屏幕引用
     */
    @Inject(
        method = "<init>",
        at = @At("RETURN")
    )
    private void onConstruct(JoinMultiplayerScreen multiplayerScreen, Minecraft minecraft, int width, int height, int top, int bottom, CallbackInfo ci) {
        this.minecraftbc$parentScreen = multiplayerScreen;
        
        // 注册服务器列表监听器
        if (MinecraftBC.getInstance() != null && MinecraftBC.getInstance().isInitialized()) {
            MinecraftBC.getInstance().getNetworkManager().addServerListListener(this::onP2PServerListReceived);
        }
    }
    
    /**
     * 当收到P2P服务器列表时
     */
    @Unique
    private void onP2PServerListReceived(List<P2PServerInfo> p2pServers) {
        Minecraft.getInstance().execute(() -> {
            MinecraftBC.getInstance().getLogger().info(
                "Received {} P2P servers, adding to list",
                p2pServers.size()
            );
            
            // 清除旧的P2P服务器项
            clearP2PServerEntries();
            
            // 添加新的P2P服务器
            for (P2PServerInfo p2pServer : p2pServers) {
                addP2PServerEntry(p2pServer);
            }
            
            // 刷新列表显示
            refreshEntries();
        });
    }
    
    /**
     * 添加P2P服务器到列表
     */
    @Unique
    private void addP2PServerEntry(P2PServerInfo p2pServer) {
        // 创建ServerData
        ServerData serverData = new ServerData(
            "[P2P] " + p2pServer.name,
            p2pServer.host + ":" + p2pServer.port,
            ServerData.Type.OTHER
        );
        
        // 标记为P2P服务器
        ((MixinServerData)(Object)serverData).minecraftbc$setP2PServer(true);
        ((MixinServerData)(Object)serverData).minecraftbc$setP2PServerId(p2pServer.id);
        ((MixinServerData)(Object)serverData).minecraftbc$setOriginalHost(p2pServer.host);
        ((MixinServerData)(Object)serverData).minecraftbc$setOriginalPort(p2pServer.port);
        
        // 设置MOTD
        serverData.motd = net.minecraft.network.chat.Component.literal(p2pServer.description);
        
        // 设置ping信息
        serverData.ping = p2pServer.latency;
        serverData.playerCount = p2pServer.playerCount;
        serverData.maxPlayers = p2pServer.maxPlayers;
        
        // 添加到列表顶部（索引0）
        // 实际实现需要使用反射或访问转换器
        addEntryAtTop(serverData);
        
        MinecraftBC.getInstance().getLogger().debug(
            "Added P2P server to list: {} ({})",
            p2pServer.name,
            p2pServer.id
        );
    }
    
    /**
     * 在列表顶部添加条目
     * 
     * 注意：这需要访问私有字段或使用反射
     */
    @Unique
    private void addEntryAtTop(ServerData serverData) {
        // 获取serverList字段
        try {
            java.lang.reflect.Field serverListField = ServerSelectionList.class.getDeclaredField("serverList");
            serverListField.setAccessible(true);
            ServerList serverList = (ServerList) serverListField.get(this);
            
            // 获取servers字段
            java.lang.reflect.Field serversField = ServerList.class.getDeclaredField("servers");
            serversField.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<ServerData> servers = (List<ServerData>) serversField.get(serverList);
            
            // 在索引0处添加
            servers.add(0, serverData);
            
        } catch (Exception e) {
            MinecraftBC.getInstance().getLogger().error("Failed to add P2P server to list: {}", e.getMessage());
        }
    }
    
    /**
     * 清除所有P2P服务器条目
     */
    @Unique
    private void clearP2PServerEntries() {
        try {
            java.lang.reflect.Field serverListField = ServerSelectionList.class.getDeclaredField("serverList");
            serverListField.setAccessible(true);
            ServerList serverList = (ServerList) serverListField.get(this);
            
            java.lang.reflect.Field serversField = ServerList.class.getDeclaredField("servers");
            serversField.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<ServerData> servers = (List<ServerData>) serversField.get(serverList);
            
            // 移除所有P2P服务器
            servers.removeIf(s -> ((MixinServerData)(Object)s).minecraftbc$isP2PServer());
            
        } catch (Exception e) {
            MinecraftBC.getInstance().getLogger().error("Failed to clear P2P servers: {}", e.getMessage());
        }
    }
    
    /**
     * 刷新列表条目
     */
    @Unique
    private void refreshEntries() {
        // 触发列表刷新
        if (minecraftbc$parentScreen != null) {
            minecraftbc$parentScreen.refreshServerList();
        }
    }
    
    /**
     * 注入updateOnlineServers方法以扫描P2P服务器
     * 
     * 在游戏执行ping扫描时，同时请求P2P服务器列表
     */
    @Inject(
        method = "updateOnlineServers",
        at = @At("HEAD")
    )
    private void onUpdateOnlineServers(ServerList serverList, CallbackInfo ci) {
        // 请求外部客户端刷新服务器列表
        if (MinecraftBC.getInstance() != null && MinecraftBC.getInstance().isInitialized()) {
            // 外部客户端会自动推送服务器列表更新
            // 这里不需要额外操作，但为了确保及时更新：
            // MinecraftBC.getInstance().getExternalClient().requestServerList();
        }
    }
}
