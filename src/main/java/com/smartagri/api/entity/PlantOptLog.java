package com.smartagri.api.entity;

import javax.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 农事操作记录实体类
 */
@Data
@Entity
@Table(name = "plant_opt_log")
public class PlantOptLog {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * 种植ID
     */
    private Long plantingId;
    
    /**
     * 操作类型（1-播种，2-施肥，3-灌溉，4-打药，5-采收，6-其他）
     */
    private Integer optType;
    
    /**
     * 操作内容
     */
    private String content;
    
    /**
     * 操作人ID
     */
    private Long operatorId;
    
    /**
     * 操作时间
     */
    private LocalDateTime optTime;
    
    /**
     * 操作地点（地块ID）
     */
    private Long landBlockId;
    
    /**
     * 操作结果
     */
    private String result;
    
    /**
     * 天气情况
     */
    private String weather;
    
    /**
     * 温度（℃）
     */
    private Double temperature;
    
    /**
     * 湿度（%）
     */
    private Double humidity;
    
    /**
     * 图片URL列表，逗号分隔
     */
    private String imageUrls;
    
    /**
     * 操作备注
     */
    private String remark;
    
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    
    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
    
    /**
     * 是否删除（0-未删除，1-已删除）
     */
    private Integer isDeleted;
} 