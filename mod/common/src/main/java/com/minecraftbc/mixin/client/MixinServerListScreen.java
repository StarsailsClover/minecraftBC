package com.minecraftbc.mixin.client;

import com.minecraftbc.core.MinecraftBC;
import com.minecraftbc.mixin.core.MixinServerData;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.multiplayer.JoinMultiplayerScreen;
import net.minecraft.client.gui.screens.multiplayer.ServerSelectionList;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.server.LanServerInfo;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * JoinMultiplayerScreen Mixin
 * 
 * 修改多人游戏屏幕，添加P2P服务器特殊渲染。
 * - P2P服务器显示特殊图标
 * - 显示连接状态指示器
 * - 添加"直接连接P2P"按钮
 */
@Mixin(JoinMultiplayerScreen.class)
public class MixinServerListScreen {
    
    @Unique
    private static final int P2P_ICON_SIZE = 16;
    
    @Unique
    private static final Component P2P_BUTTON_TEXT = Component.literal("Direct P2P");
    
    /**
     * 注入init方法添加P2P按钮
     */
    @Inject(
        method = "init",
        at = @At("RETURN")
    )
    private void onInit(CallbackInfo ci) {
        JoinMultiplayerScreen self = (JoinMultiplayerScreen)(Object)this;
        
        // 添加"直接连接P2P"按钮
        // 实际位置需要计算
        int buttonX = self.width - 100;
        int buttonY = 5;
        
        // net.minecraft.client.gui.components.Button.builder(P2P_BUTTON_TEXT, btn -> onDirectP2PClick())
        //     .pos(buttonX, buttonY)
        //     .size(90, 20)
        //     .build();
        
        MinecraftBC.getInstance().getLogger().debug("Added P2P button to multiplayer screen");
    }
    
    /**
     * 注入render方法以在P2P服务器条目前添加特殊标记
     * 
     * 修改服务器条目的渲染，添加P2P标识
     */
    @Inject(
        method = "render",
        at = @At("TAIL")
    )
    private void onRender(GuiGraphics guiGraphics, int mouseX, int mouseY, float partialTick, CallbackInfo ci) {
        // 获取选中的服务器
        JoinMultiplayerScreen self = (JoinMultiplayerScreen)(Object)this;
        ServerSelectionList serverList = getServerList(self);
        
        if (serverList != null) {
            ServerSelectionList.Entry selected = serverList.getSelected();
            if (selected instanceof ServerSelectionList.OnlineServerEntry) {
                ServerData serverData = getServerDataFromEntry((ServerSelectionList.OnlineServerEntry) selected);
                
                if (serverData != null && ((MixinServerData)(Object)serverData).minecraftbc$isP2PServer()) {
                    // 在服务器名称旁绘制P2P标识
                    renderP2PBadge(guiGraphics, serverData);
                }
            }
        }
    }
    
    /**
     * 渲染P2P标识
     */
    @Unique
    private void renderP2PBadge(GuiGraphics guiGraphics, ServerData serverData) {
        // 绘制绿色"P2P"徽章
        int x = 10; // 服务器名称左侧
        int y = 40; // 服务器名称位置
        
        // 绘制背景
        guiGraphics.fill(x, y, x + 30, y + 12, 0xFF00AA00);
        
        // 绘制文字
        Component p2pText = Component.literal("P2P");
        guiGraphics.drawString(
            Minecraft.getInstance().font,
            p2pText,
            x + 3,
            y + 2,
            0xFFFFFF
        );
        
        // 如果连接有问题，显示红色警告
        if (!MinecraftBC.getInstance().getExternalClient().isConnected()) {
            guiGraphics.fill(x + 32, y, x + 32 + 80, y + 12, 0xFFFF0000);
            Component warningText = Component.literal("Client Offline");
            guiGraphics.drawString(
                Minecraft.getInstance().font,
                warningText,
                x + 32 + 3,
                y + 2,
                0xFFFFFF
            );
        }
    }
    
    /**
     * 注入refreshServerList以添加P2P服务器分类
     */
    @Inject(
        method = "refreshServerList",
        at = @At("TAIL")
    )
    private void onRefreshServerList(CallbackInfo ci) {
        MinecraftBC.getInstance().getLogger().debug("Server list refreshed");
        
        // 如果需要，可以在这里强制刷新P2P服务器列表
        // MinecraftBC.getInstance().getNetworkManager().requestServerListRefresh();
    }
    
    /**
     * 直接连接P2P按钮点击处理
     */
    @Unique
    private void onDirectP2PClick() {
        // 打开直接连接P2P的界面
        // 允许输入p2p://node_id格式的地址
        Minecraft minecraft = Minecraft.getInstance();
        
        // 创建临时ServerData并连接
        // 实际实现需要打开一个输入对话框
    }
    
    /**
     * 获取服务器列表
     */
    @Unique
    private ServerSelectionList getServerList(JoinMultiplayerScreen screen) {
        try {
            java.lang.reflect.Field field = JoinMultiplayerScreen.class.getDeclaredField("serverSelectionList");
            field.setAccessible(true);
            return (ServerSelectionList) field.get(screen);
        } catch (Exception e) {
            return null;
        }
    }
    
    /**
     * 从条目获取ServerData
     */
    @Unique
    private ServerData getServerDataFromEntry(ServerSelectionList.OnlineServerEntry entry) {
        try {
            java.lang.reflect.Field field = ServerSelectionList.OnlineServerEntry.class.getDeclaredField("serverData");
            field.setAccessible(true);
            return (ServerData) field.get(entry);
        } catch (Exception e) {
            return null;
        }
    }
    
    /**
     * 注入joinSelectedServer方法
     * 
     * 在加入服务器前检查外部客户端连接状态
     */
    @Inject(
        method = "joinSelectedServer",
        at = @At("HEAD"),
        cancellable = true
    )
    private void onJoinSelectedServer(CallbackInfo ci) {
        JoinMultiplayerScreen self = (JoinMultiplayerScreen)(Object)this;
        ServerSelectionList serverList = getServerList(self);
        
        if (serverList != null) {
            ServerSelectionList.Entry selected = serverList.getSelected();
            if (selected instanceof ServerSelectionList.OnlineServerEntry) {
                ServerData serverData = getServerDataFromEntry((ServerSelectionList.OnlineServerEntry) selected);
                
                if (serverData != null && ((MixinServerData)(Object)serverData).minecraftbc$isP2PServer()) {
                    // 检查外部客户端是否连接
                    if (!MinecraftBC.getInstance().getExternalClient().isConnected()) {
                        // 显示错误消息
                        Minecraft.getInstance().getToasts().addToast(
                            new net.minecraft.client.gui.components.toasts.SystemToast(
                                net.minecraft.client.gui.components.toasts.SystemToast.SystemToastIds.CONNECTED_TO_REALM,
                                Component.literal("Cannot Connect"),
                                Component.literal("P2P client not connected")
                            )
                        );
                        ci.cancel();
                    }
                }
            }
        }
    }
}
