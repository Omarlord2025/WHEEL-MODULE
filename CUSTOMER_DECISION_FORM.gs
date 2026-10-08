/**
 * createWheelTrackerDecisionReviewForm()
 *
 * Builds a Google Form to put in front of the customer: Part 1 re-confirms the
 * concrete decisions already made and shipped in Wheel Tracker's real code (so
 * they can object or request a change before it's load-bearing), Part 2 surfaces
 * the 12 genuinely open questions this build left undecided (grounded in the
 * actual gaps found while building it — stock representation of partial wear,
 * acquisition cost sourcing, retirement valuation policy, Material Transfer
 * design, etc.), and Part 3 collects shape reference images.
 *
 * Run from script.google.com (paste this in, select the function, Run). First
 * run will ask you to authorize Forms access. Check the Apps Script execution
 * log (View > Logs, or Executions) for the edit/published URLs, or just look in
 * your Google Drive for the new Form.
 */
function createWheelTrackerDecisionReviewForm() {
  // دالة التحكم القسري باتجاه النص من اليمين إلى اليسار (RTL)
  function rtl(text) {
    return "‫" + text + "‬";
  }

  var form = FormApp.create(rtl('مراجعة قرارات نظام Wheel Tracker مع العميل - تأكيد المطبّق وحسم القضايا المفتوحة'));
  form.setDescription(rtl('هذا النموذج يراجع القرارات الفعلية المطبّقة في النظام الحالي (الجزء الأول) ثم يعرض 12 قضية حقيقية لم يُتخذ فيها قرار نهائي بعد (الجزء الثاني)، وأخيراً يجمع صور الأشكال القياسية برفع فعلي للملفات (الجزء الثالث).'));

  // ملاحظة: Form.setRequireLogin() غير مطلوبة هنا عمداً — هذه الدالة متاحة فقط
  // لحسابات Google Workspace (توثيق Google نفسه)، وتفشل بخطأ "This operation is
  // not supported" على أي حساب Gmail شخصي. أسئلة رفع الملفات (addFileUploadItem)
  // تفرض تسجيل الدخول تلقائياً من تلقاء نفسها عند الإجابة، دون حاجة لهذا الاستدعاء.

  form.addTextItem().setTitle(rtl('الاسم / المسمى الوظيفي (اختياري، لتتبع من اتخذ القرار)')).setRequired(false);

  // =========================================================================
  // الجزء الأول: تأكيد القرارات المطبّقة فعلياً في النظام الحالي
  // =========================================================================
  form.addSectionHeaderItem()
      .setTitle(rtl('1. تأكيد القرارات المطبّقة فعلياً في النظام'))
      .setHelpText(rtl('كل سؤال هنا يصف شيئاً يعمل بهذا الشكل بالفعل في النظام. اختر "نعم، مناسب كما هو" أو اشرح التعديل المطلوب عبر خيار (أخرى).'));

  var p1_1 = form.addCheckboxItem();
  p1_1.setTitle(rtl('1.1 الأشكال المدعومة حالياً: 1A1 (مسطح)، 1V1 (مائل بشطب واحد)، 11V9 (كأس مائل)، 12V9 (صحن مائل)، وسلسلة P (بدون قياس أبعاد). هل هذه القائمة كافية؟'))
      .setChoices([
        p1_1.createChoice(rtl('نعم، هذه كل الأشكال المستخدمة فعلياً في المصنع')),
        p1_1.createChoice(rtl('لا، هناك شكل آخر مستخدم غير مُدرج'))
      ]).showOtherOption(true).setRequired(true);

  var p1_2 = form.addMultipleChoiceItem();
  p1_2.setTitle(rtl('1.2 طريقة حساب الحجم الحالي للأشكال المسطحة تعتمد فقط على قراءة القطر الخارجي (القطر الداخلي والارتفاع يُفترض ثبوتهما). هل هذا يطابق الواقع الفعلي للتآكل؟'))
      .setChoices([
        p1_2.createChoice(rtl('نعم، يطابق - القطر الخارجي هو الوحيد الذي يتغير فعلياً')),
        p1_2.createChoice(rtl('لا، لاحظنا تغيراً في القطر الداخلي أو الارتفاع أيضاً'))
      ]).showOtherOption(true).setRequired(true);

  var p1_3 = form.addMultipleChoiceItem();
  p1_3.setTitle(rtl('1.3 نسبة الحد الأدنى القابل للاستخدام (Usable Volume Floor) الافتراضية حالياً 10%، مع إمكانية تخصيص نسبة مختلفة لكل نوع (Wheel Type) على حدة. هل 10% هي النسبة الصحيحة كافتراضي عام؟'))
      .setChoices([
        p1_3.createChoice(rtl('نعم، 10% مناسبة كافتراضي عام')),
        p1_3.createChoice(rtl('لا، يجب تغيير الافتراضي العام إلى نسبة أخرى'))
      ]).showOtherOption(true).setRequired(true);

  var p1_4 = form.addMultipleChoiceItem();
  p1_4.setTitle(rtl('1.4 عند وصول أي Wheel إلى 100% استهلاك، يقوم النظام تلقائياً وفوراً بتقاعده وإصدار إذن صرف مخزني حقيقي دون تدخل بشري. هل هذا السلوك الفوري مقبول، أم تريدون خطوة اعتماد بشري قبل إصدار إذن الصرف؟'))
      .setChoices([
        p1_4.createChoice(rtl('مقبول كما هو - تقاعد وصرف فوري وتلقائي 100%')),
        p1_4.createChoice(rtl('نريد خطوة اعتماد/مراجعة بشرية قبل إصدار إذن الصرف الفعلي'))
      ]).showOtherOption(true).setRequired(true);

  var p1_5 = form.addMultipleChoiceItem();
  p1_5.setTitle(rtl('1.5 إذا كانت عجلة واحدة قد استُخدمت على أكثر من أمر عمل (Job Card) منذ آخر قياس، يقسّم النظام حالياً تكلفة الاستهلاك بالتساوي بين كل أوامر العمل تلك. هل التقسيم المتساوي مقبول؟'))
      .setChoices([
        p1_5.createChoice(rtl('نعم، التقسيم بالتساوي مقبول وكافٍ')),
        p1_5.createChoice(rtl('لا، نريد التقسيم بالتناسب مع مدة أو كمية الاستخدام الفعلية على كل أمر'))
      ]).showOtherOption(true).setRequired(true);

  var p1_6 = form.addMultipleChoiceItem();
  p1_6.setTitle(rtl('1.6 جدول القطاعات المركبة (Compound Profile - شكل يتكون من مخروطين أو أكثر) موجود في النظام لكنه غير مُستخدم فعلياً، لأنه لا توجد بيانات حقيقية لعجلة بهذا الشكل حتى الآن. هل توجد فعلياً عجلة بهذا الشكل المركب في المصنع؟'))
      .setChoices([
        p1_6.createChoice(rtl('لا، كل العجلات الحالية بشطب واحد (قطاع واحد) فقط')),
        p1_6.createChoice(rtl('نعم، توجد عجلة بشكل مركب ونحتاج دعمها بشكل حقيقي'))
      ]).showOtherOption(true).setRequired(true);

  // =========================================================================
  // الجزء الثاني: حسم القضايا الـ 12 المفتوحة فعلياً (لم يُتخذ فيها قرار نهائي)
  // =========================================================================
  form.addPageBreakItem().setTitle(rtl('2. حسم القضايا التشغيلية والمالية الـ 12 المفتوحة'));
  form.addSectionHeaderItem()
      .setHelpText(rtl('هذه قضايا حقيقية لم يُتخذ فيها قرار نهائي بعد في بناء النظام - الإجابة هنا تحدد ما سيُبنى بعد ذلك.'));

  // --- Case 1 ---
  var c1 = form.addMultipleChoiceItem();
  c1.setTitle(rtl('القضية 1: النظام حالياً يتتبع كل عجلة ككيان كامل (Serial No) - صالحة بالكامل أو مُستهلكة بالكامل. لا توجد طريقة لرؤية "55 سم³ استُهلك من هذه العجلة" داخل تقارير مخزون ERPNext الفعلية نفسها. كيف تريدون تمثيل هذا؟'))
      .setChoices([
        c1.createChoice(rtl('لا حاجة لذلك - الأرقام الموجودة في Wheel Tracker نفسه كافية')),
        c1.createChoice(rtl('نريد تتبع الحجم المتبقي كرقم حقيقي داخل تقارير المخزون (Batch/كمية قابلة للتجزيء)')),
        c1.createChoice(rtl('نريد الحل مع إبقاء التعقيد الإضافي في حده الأدنى - اقترحوا الأنسب'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 2 ---
  var c2 = form.addMultipleChoiceItem();
  c2.setTitle(rtl('القضية 2: عند تقاعد عجلة، إذن الصرف المخزني يُسجَّل بقيمة العجلة الكاملة، بينما التكلفة الفعلية للتآكل سبق توزيعها على أوامر العمل بالتدريج أثناء الاستخدام. كيف يجب التعامل مع القيمة المالية عند التقاعد؟'))
      .setChoices([
        c2.createChoice(rtl('العجلة تُعامَل كمستلزم يُحمَّل على الحساب بالكامل من أول استلامها (لا إشكال محاسبي)')),
        c2.createChoice(rtl('العجلة أصل ثابت يُستهلك تدريجياً (إهلاك على أساس الاستخدام الفعلي) وتُشطب قيمته المتبقية فقط عند التقاعد')),
        c2.createChoice(rtl('لا داعي للمطابقة الدقيقة - الأرقام في Wheel Tracker للتحليل الإداري فقط، وليست رقماً محاسبياً نهائياً'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 3 ---
  var c3 = form.addMultipleChoiceItem();
  c3.setTitle(rtl('القضية 3: النظام حالياً يُنشئ سجل Wheel تلقائياً فقط عند عمل إذن استلام مخزني (Material Receipt) يدوي - ولا يوجد ربط مع أمر الشراء الرسمي (Purchase Order / Purchase Receipt) إن وُجد. كيف يتم شراء العجلات فعلياً في المصنع؟'))
      .setChoices([
        c3.createChoice(rtl('شراء رسمي عبر أمر شراء ثم إذن استلام (Purchase Receipt) في ERPNext')),
        c3.createChoice(rtl('استلام مباشر وتسجيل يدوي من قسم المخازن دون مرور رسمي بأمر شراء')),
        c3.createChoice(rtl('كلاهما حسب الحالة'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 4 ---
  var c4 = form.addMultipleChoiceItem();
  c4.setTitle(rtl('القضية 4: تخصيص عجلة لأمر عمل (Job Card) حالياً مجرد تغيير حالة (In Use) بدون أي حركة مخزنية فعلية - العجلة لا "تنتقل" فعلياً في سجلات ERPNext. هل تريدون ربط هذا التخصيص بحركة تحويل مخزني (Material Transfer) حقيقية؟'))
      .setChoices([
        c4.createChoice(rtl('لا حاجة - العجلة تبقى منطقياً في نفس المخزن، التخصيص الحالي كافٍ')),
        c4.createChoice(rtl('نعم، العجلة تنتقل فعلياً لموقع/ماكينة محددة ونريد تسجيل ذلك كحركة تحويل حقيقية'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 5 ---
  var c5 = form.addMultipleChoiceItem();
  c5.setTitle(rtl('القضية 5: حقول حد إعادة الطلب (Reorder Point) وكمية الطلب (Reorder Qty) لكل نوع تُدخَل يدوياً ثابتة، ولا يوجد إنشاء أمر شراء تلقائي عند الوصول للحد الأدنى - فقط تنبيه. هل هذا كافٍ؟'))
      .setChoices([
        c5.createChoice(rtl('كافٍ - التنبيه فقط، والقرار الشرائي يبقى يدوياً بالكامل')),
        c5.createChoice(rtl('نريد إنشاء مسودة أمر شراء تلقائياً عند الوصول للحد الأدنى')),
        c5.createChoice(rtl('نريد حداً متغيراً يُحسب من معدل الاستهلاك الفعلي بدلاً من رقم ثابت'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 6 ---
  var c6 = form.addMultipleChoiceItem();
  c6.setTitle(rtl('القضية 6: تصنيفات الحبيبات والتركيز والترابط (Grit / Concentration / Bond) حقول اختيارية حالياً ولا تؤثر على السعر أو حد إعادة الطلب - معلومات وصفية فقط. هل هذا مقبول؟'))
      .setChoices([
        c6.createChoice(rtl('مقبول - معلومات وصفية فقط لا تؤثر على أي حساب')),
        c6.createChoice(rtl('لا، يجب أن تكون إجبارية و/أو تؤثر على قواعد السعر وإعادة الطلب'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 7 ---
  var c7 = form.addMultipleChoiceItem();
  c7.setTitle(rtl('القضية 7: صفحة "تسجيل القياسات المجمّعة" تعرض افتراضياً كل العجلات المستخدمة في آخر 7 أيام. هل هذا المدى الزمني يطابق دورة القياس الفعلية في الصالة؟'))
      .setChoices([
        c7.createChoice(rtl('نعم، 7 أيام مناسبة')),
        c7.createChoice(rtl('لا، الدورة الفعلية أطول أو أقصر من ذلك'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 8 ---
  var c8 = form.addMultipleChoiceItem();
  c8.setTitle(rtl('القضية 8: شريط "نسبة الاستهلاك" في القوائم يتلوّن أخضر حتى 70%، أصفر/برتقالي من 70% إلى 90%، وأحمر من 90% فأعلى. هل هذه العتبات تطابق مستوى الخطورة الفعلي الذي تريدون التنبيه عنده؟'))
      .setChoices([
        c8.createChoice(rtl('نعم، العتبات الحالية (70%/90%) مناسبة')),
        c8.createChoice(rtl('لا، نريد عتبات تحذير مختلفة'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 9 ---
  var c9 = form.addMultipleChoiceItem();
  c9.setTitle(rtl('القضية 9: زر تبديل اللغة الموجود حالياً يُترجم فقط شاشات Frappe/ERPNext الأساسية - أسماء الحقول الخاصة بهذا التطبيق (Wheel، Factory Wheel Code، نسبة الاستهلاك...) تبقى بالإنجليزية دائماً. هل تريدون ترجمة كاملة لهذه الحقول أيضاً؟'))
      .setChoices([
        c9.createChoice(rtl('لا حاجة - الوضع الحالي (تبديل لغة الواجهة الأساسية فقط) كافٍ')),
        c9.createChoice(rtl('نعم، نريد ترجمة كاملة لكل حقول التطبيق الخاصة أيضاً'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 10 ---
  var c10 = form.addMultipleChoiceItem();
  c10.setTitle(rtl('القضية 10: اسم مساحة العمل في النظام هو حالياً "Grinding Wheels". هل هذا الاسم النهائي المطلوب، أم يوجد اسم تجاري/إداري آخر مفضّل؟'))
      .setChoices([
        c10.createChoice(rtl('نعم، "Grinding Wheels" هو الاسم النهائي')),
        c10.createChoice(rtl('لا، نفضّل اسماً آخر'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 11 ---
  var c11 = form.addMultipleChoiceItem();
  c11.setTitle(rtl('القضية 11: سلسلة P (عجلات التلميع/القطع) تُتابَع حالياً بفحص بصري ثنائي فقط (صالحة / غير صالحة) دون أي قياس كمي على الإطلاق. هل هذا كافٍ، أم تحتاجون مقياساً إضافياً كعدد ساعات التشغيل؟'))
      .setChoices([
        c11.createChoice(rtl('كافٍ - الفحص البصري الثنائي يكفي لهذه السلسلة')),
        c11.createChoice(rtl('نحتاج مقياساً كمياً إضافياً (مثل عدّاد ساعات التشغيل) لهذه السلسلة أيضاً'))
      ]).showOtherOption(true).setRequired(true);

  // --- Case 12 ---
  var c12 = form.addMultipleChoiceItem();
  c12.setTitle(rtl('القضية 12: تكلفة الوحدة (Unit Cost) لكل نوع عجلة تُدخَل يدوياً حالياً في Wheel Type، ولا تُسحب تلقائياً من آخر سعر شراء أو تكلفة تصنيع فعلية. هل يجب ربطها تلقائياً بمصدر مالي حقيقي؟'))
      .setChoices([
        c12.createChoice(rtl('لا، الإدخال اليدوي كافٍ ويمنحنا مرونة في التسعير')),
        c12.createChoice(rtl('نعم، يجب سحبها تلقائياً من آخر سعر شراء/تصنيع فعلي حتى تكون التكلفة دقيقة'))
      ]).showOtherOption(true).setRequired(true);

  form.addParagraphTextItem()
      .setTitle(rtl('أي ملاحظات أو قرارات أخرى لم تُذكر أعلاه؟'))
      .setRequired(false);

  // =========================================================================
  // الجزء الثالث: إرفاق صور الأشكال القياسية - رفع حقيقي عبر مجلدات Drive
  // =========================================================================
  // addFileUploadItem() في Apps Script مقيدة أيضاً بحسابات Google Workspace
  // فقط (نفس قيد setRequireLogin، توثيق Google) وتفشل بـ "is not a function"
  // على أي حساب Gmail شخصي - لا يوجد حل برمجي لإضافتها لحساب شخصي. البديل
  // الذي يعمل فعلياً على أي حساب: مجلد Drive حقيقي لكل شكل، بصلاحية "أي شخص
  // يملك الرابط يمكنه الإضافة"، مع وضع رابط كل مجلد داخل سؤاله مباشرة - هذا
  // رفع ملفات حقيقي، وليس حقل نصي يُلصق فيه رابط جاهز.
  var rootFolder = DriveApp.createFolder(
    'صور أشكال Wheel Tracker - ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm')
  );
  Logger.log('مجلد الرفع الرئيسي (لمراجعة كل الصور لاحقاً): ' + rootFolder.getUrl());

  function addShapeUploadItem(title, folderName) {
    var folder = rootFolder.createFolder(folderName);
    folder.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.EDIT);
    Logger.log('مجلد ' + folderName + ' - رابط الرفع: ' + folder.getUrl());

    form.addParagraphTextItem()
        .setTitle(rtl(title))
        .setHelpText(
          rtl('اضغط هذا الرابط وارفع الصورة مباشرة داخل المجلد (يعمل بأي حساب Google، لا حاجة لصلاحيات خاصة)، ثم اكتب هنا اسم الملف الذي رفعته للتأكيد: ') +
          folder.getUrl()
        )
        .setRequired(false);
  }

  form.addPageBreakItem().setTitle(rtl('3. إرفاق صور الأشكال القياسية للمراجعة'));
  form.addSectionHeaderItem()
      .setTitle(rtl('رفع صورة / مخطط لكل شكل مدعوم حالياً'))
      .setHelpText(rtl('كل سؤال أدناه فيه رابط مجلد Drive مخصص لهذا الشكل فقط - افتح الرابط، ارفع الصورة فيه مباشرة، ثم اكتب اسم الملف هنا للتأكيد. تنبيه: أي شخص يملك رابط المجلد يمكنه أيضاً تعديل/حذف ما بداخله - مناسب للمشاركة مع جهة معروفة وموثوقة فقط.'));

  addShapeUploadItem('3.1 صورة / مخطط شكل 1A1 (Flat Wheel)', '1A1');
  addShapeUploadItem('3.2 صورة / مخطط شكل 1V1 (Profiled Wheel)', '1V1');
  addShapeUploadItem('3.3 صورة / مخطط شكل 11V9 (Flaring Cup)', '11V9');
  addShapeUploadItem('3.4 صورة / مخطط شكل 12V9 (Dish - Beveled Wheel)', '12V9');
  addShapeUploadItem('3.5 صورة / مخطط سلسلة P-Series', 'P-Series');

  form.addSectionHeaderItem()
      .setTitle(rtl('شكل جديد غير مذكور أعلاه (إن وُجد)'))
      .setHelpText(rtl('إن أشرتم في القضية الأولى (1.1) إلى شكل غير مُدرج، اذكروا اسمه وارفعوا صورته هنا:'));

  form.addTextItem().setTitle(rtl('3.6.1 اسم الشكل الجديد')).setRequired(false);
  addShapeUploadItem('3.6.2 صورة / مخطط الشكل الجديد', 'شكل-جديد');

  // طباعة الروابط
  Logger.log('رابط تعديل النموذج: ' + form.getEditUrl());
  Logger.log('رابط معاينة النموذج (RTL): ' + form.getPublishedUrl() + '?hl=ar');
}
