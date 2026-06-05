package com.minecraftbc.mixin.core;

import com.minecraftbc.core.MinecraftBC;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.resolver.ServerAddress;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.LocalCapture;

import java.net.InetSocketAddress;

/**
 * ConnectScreen Mixin
 * 
 * 拦截连接请求，如果是P2P服务器则重定向到本地代理。
 * 
 * 工作流程：
 * 1. 玩家点击"加入服务器"
 * 2. 检查ServerData是否有P2P标记
 * 3. 如果是P2P服务器，通知外部客户端建立连接
 * 4. 等待外部客户端返回本地代理端口
 * 5. 修改连接目标为127.0.0.1:代理端口
 * 6. 游戏连接到本地代理
 * 7. 本地代理 ↔ P2P网络 ↔ 远程主机
 */
@Mixin(ConnectScreen.class)
public class MixinConnectScreen {
    
    @Unique
    private static final String P2P_PREFIX = "p2p://";
    @Unique
    private static final String LOCAL_PROXY_HOST = "127.0.0.1";
    
    /**
     * 拦截startConnecting方法
     * 
     * 目标：在建立连接前修改服务器地址
     */
    @Inject(
        method = "startConnecting",
        at = @At("HEAD"),
        cancellable = true
    )
    private static void onStartConnecting(
        Screen parent,
        Minecraft minecraft,
        ServerAddress address,
        ServerData serverData,
        CallbackInfo ci
    ) {
        // 检查是否是P2P服务器
        if (serverData != null && ((MixinServerData)(Object)serverData).minecraftbc$isP2PServer()) {
            MinecraftBC.getInstance().getLogger().info(
                "Intercepting P2P connection to {}",
                ((MixinServerData)(Object)serverData).minecraftbc$getP2PServerId()
            );
            
            // 阻止原始连接
            ci.cancel();
            
            // 获取P2P服务器信息
            String p2pServerId = ((MixinServerData)(Object)serverData).minecraftbc$getP2PServerId();
            String originalHost = ((MixinServerData)(Object)serverData).minecraftbc$getOriginalHost();
            int originalPort = ((MixinServerData)(Object)serverData).minecraftbc$getOriginalPort();
            
            // 请求外部客户端建立P2P连接
            requestP2PConnection(
                minecraft,
                parent,
                serverData,
                p2pServerId,
                originalHost,
                originalPort
            );
        }
        // 检查地址是否以p2p://开头（直接输入的地址）
        else if (address != null && address.toString().startsWith(P2P_PREFIX)) {
            MinecraftBC.getInstance().getLogger().info(
                "Detected P2P address: {}",
                address
            );
            
            // 阻止原始连接
            ci.cancel();
            
            // 解析P2P地址
            String p2pAddress = address.toString().substring(P2P_PREFIX.length());
            String[] parts = p2pAddress.split(":");
            String p2pServerId = parts[0];
            int originalPort = parts.length > 1 ? Integer.parseInt(parts[1]) : 25565;
            
            // 创建临时ServerData
            ServerData tempData = new ServerData(
                "P2P Server",
                address.toString(),
                ServerData.Type.OTHER
            );
            ((MixinServerData)(Object)tempData).minecraftbc$setP2PServer(true);
            ((MixinServerData)(Object)tempData).minecraftbc$setP2PServerId(p2pServerId);
            ((MixinServerData)(Object)tempData).minecraftbc$setOriginalHost(p2pServerId);
            ((MixinServerData)(Object)tempData).minecraftbc$setOriginalPort(originalPort);
            
            // 请求P2P连接
            requestP2PConnection(
                minecraft,
                parent,
                tempData,
                p2pServerId,
                p2pServerId,
                originalPort
            );
        }
    }
    
    /**
     * 请求P2P连接
     * 
     * 显示连接中界面，同时请求外部客户端建立P2P隧道
     */
    @Unique
    private static void requestP2PConnection(
        Minecraft minecraft,
        Screen parent,
        ServerData serverData,
        String p2pServerId,
        String originalHost,
        int originalPort
    ) {
        // 创建连接中屏幕
        ConnectScreen connectScreen = new ConnectScreen(
            parent,
            minecraft,
            serverData,
            false
        );
        minecraft.setScreen(connectScreen);
        
        // 请求外部客户端建立连接
        MinecraftBC.getInstance().getExternalClient().requestConnect(
            p2pServerId,
            originalHost,
            originalPort
        );
        
        // 设置回调，当P2P连接就绪时继续连接
        MinecraftBC.getInstance().getNetworkManager().addServerListListener(servers -> {
            // 查找对应的服务器
            for (var server : servers) {
                if (server.id.equals(p2pServerId)) {
                    // P2P连接已就绪，连接到本地代理
                    connectToLocalProxy(
                        minecraft,
                        connectScreen,
                        serverData,
                        server.host,
                        server.port
                    );
                    break;
                }
            }
        });
        
        // 设置超时
        new Thread(() -> {
            try {
                Thread.sleep(30000); // 30秒超时
                if (minecraft.screen == connectScreen) {
                    minecraft.execute(() -> {
                        minecraft.setScreen(parent);
                        minecraft.getToasts().addToast(new net.minecraft.client.gui.components.toasts.SystemToast(
                            net.minecraft.client.gui.components.toasts.SystemToast.SystemToastIds.CONNECTED_TO_REALM,
                            net.minecraft.network.chat.Component.literal("P2P Connection Failed"),
                            net.minecraft.network.chat.Component.literal("Connection timed out")
                        ));
                    });
                }
            } catch (InterruptedException ignored) {}
        }).start();
    }
    
    /**
     * 连接到本地代理
     */
    @Unique
    private static void connectToLocalProxy(
        Minecraft minecraft,
        ConnectScreen connectScreen,
        ServerData serverData,
        String proxyHost,
        int proxyPort
    ) {
        minecraft.execute(() -> {
            // 创建新的ServerAddress指向本地代理
            ServerAddress proxyAddress = new ServerAddress(proxyHost, proxyPort);
            
            MinecraftBC.getInstance().getLogger().info(
                "Connecting to P2P server via local proxy {}:{}",
                proxyHost,
                proxyPort
            );
            
            // 保存原始地址
            String originalIp = serverData.ip;
            
            // 临时修改为代理地址
            ((MixinServerData)(Object)serverData).minecraftbc$setOriginalHost(originalIp.split(":")[0]);
            ((MixinServerData)(Object)serverData).minecraftbc$setOriginalPort(
                originalIp.contains(":") ? Integer.parseInt(originalIp.split(":")[1]) : 25565
            );
            
            // 连接到本地代理
            ConnectScreen.startConnecting(
                connectScreen.getParentScreen(),
                minecraft,
                proxyAddress,
                serverData,
                false
            );
        });
    }
    
    @Unique
    private Screen getParentScreen() {
        // 返回父屏幕（需要实际Mixin实现）
        return null;
    }
}
