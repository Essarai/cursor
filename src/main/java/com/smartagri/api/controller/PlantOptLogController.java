package com.smartagri.api.controller;

import com.smartagri.api.entity.PlantOptLog;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.ArrayList;
import java.util.List;

/**
 * 农事记录Controller
 */
@RestController
@RequestMapping("/api/v1/plant-opt-log")
@Tag(name = "农事记录", description = "农事操作记录的增删改查接口")
public class PlantOptLogController {

    /**
     * 创建农事记录
     */
    @PostMapping
    @Operation(summary = "创建农事记录")
    public ResponseEntity<PlantOptLog> createPlantOptLog(@Valid @RequestBody PlantOptLog plantOptLog) {
        // TODO: 实现创建农事记录的业务逻辑
        return ResponseEntity.ok(plantOptLog);
    }

    /**
     * 修改农事记录
     */
    @PutMapping("/{optLogId}")
    @Operation(summary = "修改农事记录")
    public ResponseEntity<PlantOptLog> updatePlantOptLog(
            @PathVariable Long optLogId,
            @Valid @RequestBody PlantOptLog plantOptLog) {
        // TODO: 实现修改农事记录的业务逻辑
        return ResponseEntity.ok(plantOptLog);
    }

    /**
     * 删除农事记录
     */
    @DeleteMapping("/{optLogId}")
    @Operation(summary = "删除农事记录")
    public ResponseEntity<Void> deletePlantOptLog(@PathVariable Long optLogId) {
        // TODO: 实现删除农事记录的业务逻辑
        return ResponseEntity.ok().build();
    }

    /**
     * 获取农事记录
     */
    @GetMapping("/{optLogId}")
    @Operation(summary = "获取农事记录")
    public ResponseEntity<PlantOptLog> getPlantOptLog(@PathVariable Long optLogId) {
        // TODO: 实现获取农事记录的业务逻辑
        return ResponseEntity.ok(new PlantOptLog());
    }

    /**
     * 获取基地（的地块）下的农事记录
     */
    @GetMapping("/list")
    @Operation(summary = "获取基地（的地块）下的农事记录")
    public ResponseEntity<List<PlantOptLog>> getPlantOptLogList(
            @Parameter(description = "基地ID") @RequestParam Long baseId,
            @Parameter(description = "地块ID") @RequestParam(required = false) Long landBlockId,
            @Parameter(description = "开始时间") @RequestParam(required = false) String startTime,
            @Parameter(description = "结束时间") @RequestParam(required = false) String endTime,
            @Parameter(description = "操作类型") @RequestParam(required = false) Integer optType) {
        // TODO: 实现获取农事记录列表的业务逻辑
        return ResponseEntity.ok(new ArrayList<>());
    }
} 