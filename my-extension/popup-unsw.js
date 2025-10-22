// --- 被注入到 UNSW 页面执行的选课函数（已自包含） ---
// TODO: 改成接收数组，里面包含多个 [courseCode, courseId, termAlias]
function startEnrollment(courseCode, courseId, termAlias) {
  // 课程映射（只包含当前要选的课程）
  const COURSE_ID_MAP = {};
  COURSE_ID_MAP[courseCode] = courseId;

  // -----------------------------------------------------------------
  // 新增：学期别名映射
  // 你可以根据需要修改这里的 ID (ID会变化，例如 5263 可能是 2026 T1)
  // -----------------------------------------------------------------
  const TERM_MAP = {
    // --- 2026 ---
    "2026_Summer": "5262",
    "2026_T1": "5263",
    "2026_T2": "5266",
    "2026_T3": "5269",
    // --- 简写 (指向 2026) ---
    Summer: "5262",
    T1: "5263",
    T2: "5266",
    T3: "5269",
    // 你可以继续添加其他年份或别名
  };

  // 辅助：睡眠
  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  // 尝试切换到指定学期（多策略）
  async function ensureTermActive(selector, timeout = 7000) {
    if (!selector) {
      console.log("未提供学期选择器，使用当前激活学期。");
      return true;
    }

    console.log(`尝试切换到学期: ${selector}`);

    // 若传入的是完整 link id（如 "term5263Link" 或 "term5263Link"）
    let linkId = selector;
    if (!/^term\d+Link$/.test(linkId) && /^\d+$/.test(selector)) {
      // 支持传入 "5263" → 变成 "term5263Link"
      linkId = `term${selector}Link`;
    }

    const tryClickLink = () => {
      const el = document.getElementById(linkId);
      if (el) {
        console.log(`找到学期链接元素 id=${linkId}，尝试点击切换学期`);
        el.click();
        return true;
      }
      // 也尝试直接以 selector 当作 id 点击
      const el2 = document.getElementById(selector);
      if (el2) {
        console.log(`找到学期链接元素 id=${selector}，尝试点击切换学期`);
        el2.click();
        return true;
      }
      return false;
    };

    // 如果页面提供全局函数 selectTerm(id)，优先调用（HTML 片段中有）
    try {
      if (typeof window.selectTerm === "function") {
        // selector 可能是 "5263" 或 "term5263"
        const idNumMatch = selector.match(/\d+/);
        if (idNumMatch) {
          console.log(
            `调用页面内置 selectTerm(${idNumMatch[0]}) 切换学期（如果存在）`
          );
          window.selectTerm(idNumMatch[0]);
        }
      }
    } catch (e) {
      console.warn("调用 selectTerm 失败：", e);
    }

    // 尝试点击 link（如果存在）
    tryClickLink();

    // 等待 active form 出现或 term input 更新，轮询直到超时
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const activeForm = document.querySelector("div.tab-pane.active form");
      if (activeForm) {
        // 看看 activeForm 里是否有 input[name="term"] 且值匹配 selector（若 selector 看起来像 term 值）
        const termInput = activeForm.querySelector('input[name="term"]');
        if (!selector) return true;
        if (
          termInput &&
          (termInput.value === selector || termInput.value.includes(selector))
        ) {
          console.log("已切换到目标学期（通过 active form 的 term 值匹配）。");
          return true;
        }
        // 如果 activeForm 存在但我们只是想切换标签，那么认为切换成功
        if (
          document.querySelector(`#${linkId}.active`) ||
          document.querySelector("div.tab-pane.active")
        ) {
          // 允许继续（有时无法精确匹配 term 字段）
          console.log("检测到激活的学期标签（未严格匹配 term 值），继续。");
          return true;
        }
      }
      await sleep(250);
    }

    console.warn(
      "切换学期超时或未找到目标学期元素，脚本将尝试在当前激活学期继续。"
    );
    return false;
  }

  // 找到当前激活表单（等候直到出现或直接返回 null）
  async function waitForActiveForm(timeout = 7000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const activeForm = document.querySelector("div.tab-pane.active form");
      if (activeForm) {
        const seq = activeForm.querySelector('input[name="bsdsSequence"]');
        const term = activeForm.querySelector('input[name="term"]');
        if (seq && term) {
          return { activeForm, sequenceInput: seq, termInput: term };
        }
        // 如果表单存在但缺少字段也返回以便脚本处理
        return {
          activeForm,
          sequenceInput: seq || null,
          termInput: term || null,
        };
      }
      await sleep(200);
    }
    return null;
  }

  // --- 步骤 0：搜索课程（支持 forcedTerm） ---
  async function runStep0_SearchCourse(courseCode, activeFormInfo, forcedTerm) {
    console.log("=== 步骤 0：搜索课程 ===");
    if (!activeFormInfo || !activeFormInfo.activeForm) {
      alert("❌ 找不到激活的表单，请确保在正确的学期标签页或学期已加载。");
      return null;
    }

    const { activeForm, sequenceInput, termInput } = activeFormInfo;

    if (!sequenceInput) {
      alert("❌ 找不到必要的表单字段（bsdsSequence），请检查页面结构。");
      return null;
    }

    // 优先使用 forcedTerm（来自 TERM_MAP），否则回退到页面值
    const termValue = forcedTerm || (termInput ? termInput.value : "");

    const searchPayload = {
      bsdsSequence: sequenceInput.value,
      term: termValue,
      search: courseCode,
      "bsdsSubmit-search-courses": "Search",
    };

    console.log("发送搜索请求:", searchPayload);

    try {
      const response = await fetch(
        "https://my.unsw.edu.au/active/studentClassEnrol/courses.xml",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams(searchPayload),
          credentials: "same-origin", // 确保携带 cookies
        }
      );

      if (!response.ok) {
        alert(`❌ 搜索失败: ${response.status} ${response.statusText}`);
        return null;
      }

      const searchResultHtml = await response.text();
      console.log("✅ 搜索成功！");

      const sequenceMatch = searchResultHtml.match(
        /<input type="hidden" name="bsdsSequence" value="(\d+)"/
      );

      if (!sequenceMatch) {
        alert("❌ 无法从搜索结果中提取 bsdsSequence");
        return null;
      }

      const newSequence = sequenceMatch[1];
      console.log(`✅ 获取到新令牌: ${newSequence}`);

      return {
        sequence: newSequence,
        termValue: termValue,
      };
    } catch (error) {
      alert("❌ 搜索请求网络错误: " + error.message);
      return null;
    }
  }

  // --- 步骤 1：提交课程选择（支持 forcedTerm） ---
  async function runStep1_SubmitCourse(courseCode, searchData, forcedTerm) {
    console.log("=== 步骤 1：提交课程选择 ===");
    if (!COURSE_ID_MAP[courseCode]) {
      alert(`❌ 课程代码 ${courseCode} 没有对应的课程ID`);
      return null;
    }
    const courseId = COURSE_ID_MAP[courseCode];
    console.log(`使用课程ID: ${courseId}`);

    // 使用 searchData.sequence，并用 forcedTerm 覆盖或回退到 searchData.termValue
    const termValue = forcedTerm || (searchData && searchData.termValue) || "";

    const submitPayload = {
      bsdsSequence: searchData.sequence,
      term: termValue,
      course: "",
      class: "",
      "selectCourses[]": courseId,
      search: courseCode,
      "bsdsSubmit-submit-courses": "Confirm Enrolment Request",
    };

    console.log("发送课程提交请求:", submitPayload);

    try {
      const response = await fetch(
        "https://my.unsw.edu.au/active/studentClassEnrol/courses.xml",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams(submitPayload),
          credentials: "same-origin",
        }
      );

      if (!response.ok) {
        alert(`❌ 提交失败: ${response.status} ${response.statusText}`);
        return null;
      }

      const confirmPageHtml = await response.text();
      console.log("✅ 成功进入确认页面");

      const sequenceMatch = confirmPageHtml.match(
        /<input type="hidden" name="bsdsSequence" value="(\d+)"/
      );

      if (!sequenceMatch) {
        alert("❌ 无法从确认页面提取 bsdsSequence");
        return null;
      }

      const confirmSequence = sequenceMatch[1];
      console.log(`✅ 获取到确认令牌: ${confirmSequence}`);

      return { confirmSequence, termValue };
    } catch (error) {
      alert("❌ 提交请求网络错误: " + error.message);
      return null;
    }
  }

  // --- 步骤 2：最终确认注册（支持 forcedTerm，并短重试） ---
  async function runStep2_ConfirmEnrolment(confirmSequence, forcedTerm) {
    console.log("=== 步骤 2：最终确认注册 ===");
    const confirmPayload = {
      bsdsSequence: confirmSequence,
      term: forcedTerm || "",
      "bsdsSubmit-confirm": "Submit Enrolment Request",
    };

    console.log("发送最终确认请求:", confirmPayload);

    // 短重试（2 次）
    const maxAttempts = 2;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const response = await fetch(
          "https://my.unsw.edu.au/active/studentClassEnrol/confirm.xml",
          {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams(confirmPayload),
            credentials: "same-origin",
          }
        );

        if (!response.ok) {
          console.warn(`确认请求返回 ${response.status}（尝试 ${attempt}）`);
          if (response.status === 403 && attempt < maxAttempts) {
            await sleep(300);
            continue;
          }
          alert(`❌ 确认失败: ${response.status} ${response.statusText}`);
          return { success: false, status: response.status };
        }

        const resultHtml = await response.text();
        console.log("✅ 已收到最终结果页面");

        if (
          resultHtml.includes("badge-success") &&
          (resultHtml.includes("Success") ||
            resultHtml.includes("Enrolment Results"))
        ) {
          console.log("🎉🎉🎉 注册成功！🎉🎉🎉");
          alert("✅ 选课成功！");
          document.open();
          document.write(resultHtml);
          document.close();
          return { success: true };
        } else if (
          resultHtml.includes("badge-danger") ||
          resultHtml.includes("Error")
        ) {
          console.error("❌❌❌ 注册失败！❌❌❌");
          alert("❌ 选课失败！可能原因：课程已满、时间冲突或先修课程未满足");
          document.open();
          document.write(resultHtml);
          document.close();
          return { success: false, status: "enrol_failed" };
        } else {
          console.warn("⚠️ 结果未知");
          alert("⚠️ 请求已提交，请查看页面结果");
          document.open();
          document.write(resultHtml);
          document.close();
          return { success: false, status: "unknown" };
        }
      } catch (error) {
        alert("❌ 确认请求网络错误: " + error.message);
        return { success: false, status: "network_error" };
      }
    }

    return { success: false, status: "max_attempts" };
  }

  // 主流程（使用 forced termSelector，并在失败时尝试一次完整重试）
  async function autoEnroll(courseCode, termAlias) {
    console.log("=".repeat(60));
    console.log(`🚀 开始自动选课流程: ${courseCode} (学期: ${termAlias})`);
    console.log("=".repeat(60));

    // -----------------------------------------------------------------
    // 修改：从 MAP 中查找学期 ID
    // -----------------------------------------------------------------
    const termSelector = TERM_MAP[termAlias];
    if (!termSelector) {
      alert(`❌ 错误：未知的学期别名 "${termAlias}"。请检查 TERM_MAP。`);
      console.error(`流程终止：未知的学期别名 ${termAlias}`);
      return;
    }
    console.log(`查询到学期 ID: ${termSelector}`);

    // 如果传了 termSelector，先尝试切换学期
    await ensureTermActive(termSelector); // <--- 使用查询到的 termSelector

    // 等待激活表单加载
    let activeFormInfo = await waitForActiveForm();
    if (!activeFormInfo) {
      alert("❌ 等待激活表单超时，无法继续。");
      console.error("流程终止：找不到激活表单");
      return;
    }

    // 额外等待：确保 activeForm 的 termInput.value 实际包含目标学期 id（最多等 5 秒）
    if (activeFormInfo.termInput) {
      const start = Date.now();
      while (Date.now() - start < 5000) {
        if (
          activeFormInfo.termInput.value &&
          activeFormInfo.termInput.value.includes(termSelector)
        ) {
          console.log("确认 active form 的 term 字段已更新为目标学期。");
          break;
        }
        await sleep(250);
        activeFormInfo = (await waitForActiveForm(2000)) || activeFormInfo;
      }
      if (
        !(
          activeFormInfo.termInput &&
          activeFormInfo.termInput.value.includes(termSelector)
        )
      ) {
        console.warn(
          "active form 的 term 未能精确匹配目标学期，脚本将强制在请求中使用目标学期 ID。"
        );
      }
    } else {
      console.warn(
        "active form 没有 termInput 字段，脚本将强制在请求中使用目标学期 ID。"
      );
    }

    // 执行一次完整流程（search → submit → confirm），在 confirm 失败时会重试一次完整流程
    async function runFullOnce() {
      const searchData = await runStep0_SearchCourse(
        courseCode,
        activeFormInfo,
        termSelector
      );
      if (!searchData) {
        console.error("流程终止：搜索失败");
        return { success: false, stage: "search" };
      }

      await sleep(300);

      const submitResult = await runStep1_SubmitCourse(
        courseCode,
        searchData,
        termSelector
      );
      if (!submitResult || !submitResult.confirmSequence) {
        console.error("流程终止：提交课程失败");
        return { success: false, stage: "submit" };
      }

      await sleep(300);

      const confirmResult = await runStep2_ConfirmEnrolment(
        submitResult.confirmSequence,
        termSelector
      );
      return confirmResult;
    }

    // 第一次尝试
    let attemptResult = await runFullOnce();

    // 如果 confirm 返回看起来是 token/403 等问题，则再尝试一次完整流程
    if (
      !attemptResult.success &&
      (attemptResult.status === 403 ||
        attemptResult.status === "max_attempts" ||
        attemptResult.stage === "submit")
    ) {
      console.warn(
        "首次尝试可能因 token/403/短暂错误失败，正在重试一次完整流程..."
      );
      await sleep(300);
      // 刷新 activeFormInfo（以防页面发生变更）
      activeFormInfo = (await waitForActiveForm()) || activeFormInfo;
      attemptResult = await runFullOnce();
    }

    if (attemptResult.success) {
      console.log("✅ 选课流程完成：成功");
    } else {
      console.log("❌ 选课流程完成：失败", attemptResult);
    }

    console.log("=".repeat(60));
  }

  // -----------------------------------------------------------------
  // 修改：调用 autoEnroll 时传入 termAlias
  // -----------------------------------------------------------------
  autoEnroll(courseCode, termAlias);
}
