/**
 * The admin section in plain browser JavaScript: no module, no bundler.
 *
 * The page is complete without this file; the server rendered every banner
 * with the real state. This file adds two things:
 *   1. "Check again": asks GET admin/state, shows the banner of the new
 *      state, replaces versions and time as text and moves the focus to the
 *      state area; a failed request shows the warning banner on top,
 *   2. the test result switch (debug mode only): POST admin/sample on every
 *      change, "Saved" for three seconds, or the error text and the old value,
 *   3. profile, computing time and models (05-UI-SPEC): the profile and the
 *      offline switch are saved on every change, threads and window with one
 *      button after a check in the browser, and while a model is waiting,
 *      downloading or being verified GET admin/resources is asked every five
 *      seconds, only on a visible page, never twice at once, and no more
 *      after three failures in a row.
 *
 * It flips hidden attributes and replaces text, it never builds markup. The
 * request token is read out of the document for every call, because the
 * server rotates it when the session is renewed. Every translated word comes
 * out of a data attribute the template filled.
 */
'use strict'

;(function () {
  const root = document.getElementById('avs-admin')
  const stateArea = document.getElementById('avs-backend-state')
  if (root === null || stateArea === null) {
    return
  }

  const STATES = ['ok', 'version_patch_differs', 'version_drift', 'backend_missing', 'backend_disabled', 'backend_unreachable', 'no_app_api']
  const SAVED_FOR_MS = 3000
  const unknown = root.dataset.unknown || ''

  function url (path) {
    return OC.generateUrl('/apps/audio_video_search/' + path)
  }

  async function ask (path) {
    const response = await fetch(url(path), {
      credentials: 'same-origin',
      headers: {
        requesttoken: document.head.dataset.requesttoken,
        Accept: 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error('audio_video_search: ' + response.status)
    }

    return response.json()
  }

  // The answer of a POST with its status, whatever it is: a refusal of the
  // resources route carries a body the page shows (400 field, 409 locked).
  async function post (path, payload) {
    const response = await fetch(url(path), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        requesttoken: document.head.dataset.requesttoken,
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      body: JSON.stringify(payload)
    })
    let body = null
    try {
      body = await response.json()
    } catch (ignored) {
      body = null
    }

    return { status: response.status, body }
  }

  async function send (path, payload) {
    const answer = await post(path, payload)
    if (answer.status < 200 || answer.status > 299) {
      throw new Error('audio_video_search: ' + answer.status)
    }

    return answer.body
  }

  function setText (nodes, value) {
    for (const node of nodes) {
      node.textContent = value
    }
  }

  function version (value) {
    return typeof value === 'string' && value !== '' ? value : unknown
  }

  // The locale of the admin as the server put it on the root element.
  function clock (seconds) {
    const date = new Date(seconds * 1000)
    const locale = (document.documentElement.dataset.locale || document.documentElement.lang || '').replace('_', '-')
    try {
      return date.toLocaleTimeString(locale || undefined)
    } catch (ignored) {
      return date.toLocaleTimeString()
    }
  }

  // -- "Check again" ---------------------------------------------------------

  const button = document.getElementById('avs-recheck')
  const label = document.getElementById('avs-recheck-label')
  const spinner = document.getElementById('avs-recheck-spinner')
  const failed = document.getElementById('avs-recheck-failed')
  const checkedAt = document.getElementById('avs-checked-at')
  const emptyHint = document.getElementById('avs-sample-empty')
  const banners = stateArea.querySelectorAll('[data-state]')
  const idleText = label !== null ? label.textContent : ''

  function busy (on) {
    button.disabled = on
    if (spinner !== null) {
      spinner.hidden = !on
    }
    if (label !== null) {
      label.textContent = on ? (button.dataset.checking || idleText) : idleText
    }
    if (on) {
      stateArea.setAttribute('aria-busy', 'true')
    } else {
      stateArea.removeAttribute('aria-busy')
    }
  }

  function show (answer) {
    for (const banner of banners) {
      banner.hidden = banner.dataset.state !== answer.state
    }
    setText(root.querySelectorAll('.avs-version-own'), version(answer.own))
    setText(root.querySelectorAll('.avs-version-backend'), version(answer.backend))
    if (checkedAt !== null && Number.isInteger(answer.checkedAt)) {
      checkedAt.textContent = clock(answer.checkedAt)
      checkedAt.setAttribute('datetime', new Date(answer.checkedAt * 1000).toISOString())
    }
    if (emptyHint !== null) {
      // Only a reported zero means "none yet"; an unknown count says nothing.
      emptyHint.hidden = answer.sampleCount !== 0
    }
  }

  if (button !== null) {
    button.addEventListener('click', async function () {
      busy(true)
      try {
        const answer = await ask('admin/state')
        if (answer === null || typeof answer !== 'object' || !STATES.includes(answer.state)) {
          throw new Error('audio_video_search: unknown state')
        }
        show(answer)
        if (failed !== null) {
          failed.hidden = true
        }
      } catch (error) {
        // The last banner stays; the warning says it is not fresh.
        if (failed !== null) {
          failed.hidden = false
        }
      } finally {
        busy(false)
        stateArea.focus()
      }
    })
  }

  // -- profile, computing time, models --------------------------------------------

  const PROFILES = ['fast', 'balanced', 'quality']
  const MODELS = ['parakeet', 'silero', 'whisper-turbo', 'whisper-large-v3']
  const MODEL_STATES = [
    'in_image', 'present', 'not_needed', 'waiting', 'downloading', 'verifying',
    'wrong_digest_download', 'wrong_digest_placed', 'offline_missing', 'failed', 'disk_full'
  ]
  const POLLED_STATES = ['waiting', 'downloading', 'verifying']
  const POLL_EVERY_MS = 5000
  const POLL_FAILURES = 3
  const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

  // The rule of ResourceFormat::gigabytes in PHP, on the same whole tenths of
  // a GB (10^8 bytes): a need is rounded up, what is available down, a size
  // half up. test_admin_phase5_assets.py holds both rules to the same numbers.
  function gigabytes (bytes, mode, unit, decimal) {
    const TENTH = 100000000
    const amount = Math.max(0, bytes)
    let tenths
    if (mode === 'need') {
      tenths = Math.floor((amount + TENTH - 1) / TENTH)
    } else if (mode === 'available') {
      tenths = Math.floor(amount / TENTH)
    } else {
      tenths = Math.floor((amount + TENTH / 2) / TENTH)
    }

    return unit.replace('%s', Math.floor(tenths / 10) + decimal + (tenths % 10))
  }

  // Only what the page reads; the PHP side checked the contract shape.
  function usable (answer) {
    const part = function (value) {
      return value !== null && typeof value === 'object'
    }

    return part(answer) && Array.isArray(answer.profiles) && Array.isArray(answer.models) &&
      Array.isArray(answer.zones) && part(answer.threads) && part(answer.window) && part(answer.offline)
  }

  // What the server rendered the page from (initial state "resources").
  function initial () {
    const field = document.getElementById('initial-state-audio_video_search-resources')
    if (field === null) {
      return null
    }
    try {
      const answer = JSON.parse(window.atob(field.value))

      return usable(answer) ? answer : null
    } catch (ignored) {
      return null
    }
  }

  const profileRoot = document.getElementById('avs-profile')
  let current = profileRoot !== null ? initial() : null

  // Without a readable answer (backend silent, R9) the sections stay as the
  // server rendered them: nothing to save, nothing to ask.
  if (current !== null) {
    const unit = profileRoot.dataset.unit || '%s GB'
    const decimal = profileRoot.dataset.decimal === ',' ? ',' : '.'
    const unknownAmount = profileRoot.dataset.unknown || unknown

    const options = document.getElementById('avs-profile-options')
    const profileStatus = document.getElementById('avs-profile-status')
    const lowBanner = document.getElementById('avs-profile-low')
    const fallbackBanner = document.getElementById('avs-profile-fallback')
    const intro = document.getElementById('avs-profile-intro')
    const form = document.getElementById('avs-compute-form')
    const threads = document.getElementById('avs-threads')
    const threadsError = document.getElementById('avs-threads-error')
    const windowAlways = document.getElementById('avs-window-always')
    const windowSet = document.getElementById('avs-window-set')
    const windowFields = document.getElementById('avs-window-fields')
    const windowStart = document.getElementById('avs-window-start')
    const windowEnd = document.getElementById('avs-window-end')
    const windowZone = document.getElementById('avs-window-zone')
    const windowError = document.getElementById('avs-window-error')
    const windowState = document.getElementById('avs-window-state')
    const save = document.getElementById('avs-compute-save')
    const computeStatus = document.getElementById('avs-compute-status')
    const stale = document.getElementById('avs-models-stale')
    const live = document.getElementById('avs-models-live')
    const offline = document.getElementById('avs-offline')
    const offlineStatus = document.getElementById('avs-offline-status')
    const offlineForced = document.getElementById('avs-offline-forced')

    const statusTimers = new Map()
    const shownStates = {}
    // Requests of the admin that are on their way: an answer of the polling
    // that arrives meanwhile is not shown, the answer of the request follows.
    let saving = 0

    function hide (node, hidden) {
      if (node !== null) {
        node.hidden = hidden
      }
    }

    // A status text; a fleeting one ("Saved") goes after three seconds.
    function tell (node, text, fleeting) {
      if (node === null) {
        return
      }
      window.clearTimeout(statusTimers.get(node))
      node.textContent = text
      if (fleeting) {
        statusTimers.set(node, window.setTimeout(function () {
          node.textContent = ''
        }, SAVED_FOR_MS))
      }
    }

    // A translated word the template put into a data attribute of a status.
    function word (node, key) {
      return node !== null ? node.dataset[key] || '' : ''
    }

    function fill (key, value) {
      setText(document.querySelectorAll('[data-value="' + key + '"]'), value)
    }

    function amount (bytes, mode) {
      return Number.isInteger(bytes) ? gigabytes(bytes, mode, unit, decimal) : unknownAmount
    }

    // The translated name of a profile, as the server printed it at its radio.
    function profileName (id) {
      const node = document.querySelector('[data-profile-name="' + id + '"]')

      return node !== null ? node.textContent : unknownAmount
    }

    // Add an id to aria-describedby of a field, or take it out again.
    function describe (field, id, on) {
      const ids = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(function (entry) {
        return entry !== '' && entry !== id
      })
      if (on) {
        ids.push(id)
      }
      field.setAttribute('aria-describedby', ids.join(' '))
    }

    function mark (field, errorId, on) {
      if (field === null) {
        return
      }
      if (on) {
        field.setAttribute('aria-invalid', 'true')
      } else {
        field.removeAttribute('aria-invalid')
      }
      describe(field, errorId, on)
    }

    function announce (changes) {
      if (live === null || changes.length === 0) {
        return
      }
      live.textContent = changes.join(' ')
    }

    // Every number, lock and state of the three sections out of one answer:
    // the same function after a save and after a poll. It reads the same
    // rules as the template (R1, R2, R3).
    function render (answer) {
      const available = Number.isInteger(answer.availableBytes) ? answer.availableBytes : null
      const proposed = PROFILES.includes(answer.proposed) ? answer.proposed : 'none'
      const chosen = PROFILES.includes(answer.chosen) ? answer.chosen : null
      const effective = PROFILES.includes(answer.effective) ? answer.effective : 'none'
      // R2, fail safe: an unknown amount locks every profile.
      const low = available === null || !Number.isInteger(answer.minimumBytes) ||
        available < answer.minimumBytes || proposed === 'none'
      const lockedByAnswer = {}
      const needs = {}
      for (const profile of answer.profiles) {
        if (profile !== null && typeof profile === 'object' && PROFILES.includes(profile.id)) {
          lockedByAnswer[profile.id] = profile.locked !== false
          needs[profile.id] = profile.needBytes
        }
      }
      const fallback = !low && chosen !== null && lockedByAnswer[chosen] !== false &&
        effective !== 'none' && effective !== chosen
      const checkedProfile = chosen !== null ? chosen : (effective !== 'none' ? effective : null)
      const chosenName = chosen !== null ? profileName(chosen) : unknownAmount

      fill('available', amount(available, 'available'))
      fill('minimum', amount(answer.minimumBytes, 'need'))
      fill('proposed-name', proposed !== 'none' ? profileName(proposed) : unknownAmount)
      fill('chosen-name', chosenName)
      fill('chosen-need', chosen !== null ? amount(needs[chosen], 'need') : unknownAmount)
      fill('effective-name', effective !== 'none' ? profileName(effective) : chosenName)
      hide(lowBanner, !low)
      hide(fallbackBanner, !fallback)
      hide(intro, low)
      if (options !== null) {
        if (low) {
          options.removeAttribute('aria-describedby')
        } else {
          options.setAttribute('aria-describedby', 'avs-profile-intro')
        }
      }
      for (const id of PROFILES) {
        const locked = low || lockedByAnswer[id] !== false
        const radio = document.getElementById('avs-profile-' + id)
        fill('need-' + id, amount(needs[id], 'need'))
        hide(document.getElementById('avs-profile-' + id + '-need'), locked)
        hide(document.getElementById('avs-profile-' + id + '-lock'), !locked)
        hide(document.querySelector('[data-badge="' + id + '"]'), low || proposed !== id)
        if (radio !== null) {
          radio.checked = checkedProfile === id
          radio.disabled = locked
          radio.setAttribute('aria-describedby', 'avs-profile-' + id + '-desc avs-profile-' + id + (locked ? '-lock' : '-need'))
        }
      }

      // Computing time: the ceiling and the line of the stored window. What
      // the admin is typing into the form is left alone.
      if (threads !== null && Number.isInteger(answer.threads.standard)) {
        threads.max = String(answer.threads.standard)
      }
      const stored = typeof answer.window.start === 'string' && typeof answer.window.end === 'string'
      hide(windowState, !stored)
      if (windowState !== null) {
        hide(windowState.querySelector('[data-window="open"]'), answer.window.openNow !== true)
        hide(windowState.querySelector('[data-window="closed"]'), answer.window.openNow === true)
      }
      fill('change-at', typeof answer.window.changeAt === 'string' ? answer.window.changeAt : unknownAmount)

      // Models: one state line visible, the bar only while downloading.
      const changes = []
      for (const id of MODELS) {
        const model = answer.models.find(function (entry) {
          return entry !== null && typeof entry === 'object' && entry.id === id
        })
        const box = document.querySelector('.avs-models__state[data-model="' + id + '"]')
        if (model === undefined || box === null) {
          continue
        }
        const state = MODEL_STATES.includes(model.state) ? model.state : 'failed'
        fill('size-' + id, amount(model.totalBytes, 'size'))
        fill('done-' + id, amount(model.doneBytes, 'size'))
        fill('free-' + id, amount(model.needFreeBytes, 'need'))
        let sentence = ''
        for (const line of box.querySelectorAll('[data-state]')) {
          line.hidden = line.dataset.state !== state
          if (!line.hidden && line.lastElementChild !== null) {
            sentence = line.lastElementChild.textContent
          }
        }
        const bar = box.querySelector('progress')
        if (bar !== null && Number.isInteger(model.totalBytes) && Number.isInteger(model.doneBytes)) {
          bar.max = model.totalBytes
          bar.value = Math.min(model.doneBytes, model.totalBytes)
          bar.hidden = state !== 'downloading'
        }
        // Only a change of state is said, never a step of the download.
        if (shownStates[id] !== undefined && shownStates[id] !== state) {
          const name = document.getElementById('avs-model-' + id + '-name')
          changes.push((name !== null ? name.textContent + '. ' : '') + sentence)
        }
        shownStates[id] = state
      }
      announce(changes)

      // Offline: set by the deploy option it is on and never operable.
      if (offline !== null) {
        const forced = answer.offline.forcedByEnv === true
        offline.checked = forced || answer.offline.value === true
        offline.disabled = forced
        hide(offlineForced, !forced)
        describe(offline, 'avs-offline-forced', forced)
      }
    }

    function take (answer) {
      current = answer
      render(answer)
    }

    // -- polling ---------------------------------------------------------------

    let pollTimer = null
    let pollBusy = false
    let pollFailures = 0
    let pollStopped = false

    function downloadPending () {
      return current.models.some(function (model) {
        return model !== null && typeof model === 'object' && POLLED_STATES.includes(model.state)
      })
    }

    // One timer at most, and none while a request is on its way: the next
    // one is set only after the answer, so two never overlap.
    function schedule () {
      window.clearTimeout(pollTimer)
      pollTimer = null
      if (pollStopped || pollBusy || !downloadPending() || document.visibilityState !== 'visible') {
        return
      }
      pollTimer = window.setTimeout(poll, POLL_EVERY_MS)
    }

    async function poll () {
      pollTimer = null
      if (pollStopped || pollBusy || document.visibilityState !== 'visible') {
        return
      }
      pollBusy = true
      try {
        const answer = await ask('admin/resources')
        if (!usable(answer)) {
          throw new Error('audio_video_search: unknown resources')
        }
        pollFailures = 0
        if (saving === 0) {
          take(answer)
        }
      } catch (error) {
        pollFailures += 1
        if (pollFailures >= POLL_FAILURES) {
          // The last state stays; the warning says it is not fresh (R10).
          pollStopped = true
          hide(stale, false)
        }
      } finally {
        pollBusy = false
        schedule()
      }
    }

    document.addEventListener('visibilitychange', schedule)

    // -- the profile: saved on every change ---------------------------------------

    function profileBusy (on) {
      if (options !== null) {
        if (on) {
          options.setAttribute('aria-busy', 'true')
        } else {
          options.removeAttribute('aria-busy')
        }
      }
    }

    for (const id of PROFILES) {
      const radio = document.getElementById('avs-profile-' + id)
      if (radio === null) {
        continue
      }
      radio.addEventListener('change', async function () {
        saving += 1
        profileBusy(true)
        for (const other of PROFILES) {
          const node = document.getElementById('avs-profile-' + other)
          if (node !== null) {
            node.disabled = true
          }
        }
        tell(profileStatus, '', false)
        let answer = null
        try {
          answer = await post('admin/resources', { profile: id })
        } catch (error) {
          answer = null
        }
        saving -= 1
        profileBusy(false)
        if (answer !== null && answer.status === 200 && usable(answer.body)) {
          take(answer.body)
          tell(profileStatus, word(profileStatus, 'saved'), true)
          schedule()

          return
        }
        if (answer !== null && answer.status === 409 && answer.body !== null && typeof answer.body === 'object') {
          // Locked in the meantime: the numbers of the refusal become the lock.
          current.availableBytes = Number.isInteger(answer.body.availableBytes) ? answer.body.availableBytes : null
          for (const profile of current.profiles) {
            if (profile !== null && typeof profile === 'object' && profile.id === id) {
              profile.locked = true
              if (Number.isInteger(answer.body.needBytes)) {
                profile.needBytes = answer.body.needBytes
              }
            }
          }
          tell(profileStatus, word(profileStatus, 'locked'), false)
        } else {
          tell(profileStatus, word(profileStatus, 'failed'), false)
        }
        // The old radio and the locks of the last known answer.
        render(current)
      })
    }

    // -- computing time: one button for threads and window --------------------------

    function threadsWrong (on) {
      hide(threadsError, !on)
      mark(threads, 'avs-threads-error', on)
    }

    // code: window_same, window_time, window_zone, or null for no error.
    function windowWrong (code, fields) {
      if (windowError !== null) {
        for (const sentence of windowError.querySelectorAll('[data-error]')) {
          sentence.hidden = sentence.dataset.error !== code
        }
        windowError.hidden = code === null
      }
      for (const field of [windowStart, windowEnd, windowZone]) {
        mark(field, 'avs-window-error', fields.includes(field))
      }
    }

    // Show the error of a field code (of the browser check or of a 400
    // answer) and name the field the focus goes to; null for a foreign code.
    function wrong (code) {
      if (code === 'threads') {
        threadsWrong(true)

        return threads
      }
      if (code === 'window_start') {
        windowWrong('window_time', [windowStart])

        return windowStart
      }
      if (code === 'window_end') {
        windowWrong('window_time', [windowEnd])

        return windowEnd
      }
      if (code === 'window_same') {
        windowWrong('window_same', [windowStart, windowEnd])

        return windowStart
      }
      if (code === 'window_zone') {
        windowWrong('window_zone', [windowZone])

        return windowZone
      }

      return null
    }

    // The rules of the PHP route and of the container, in their order: threads
    // a whole number from 1 to the default, times as HH:MM, start and end
    // different, the zone one of the list.
    function findings () {
      const found = []
      const raw = threads.value.trim()
      if (!/^\d+$/.test(raw) || Number(raw) < 1 || Number(raw) > current.threads.standard) {
        found.push('threads')
      }
      if (windowSet.checked) {
        if (!TIME.test(windowStart.value)) {
          found.push('window_start')
        } else if (!TIME.test(windowEnd.value)) {
          found.push('window_end')
        } else if (windowStart.value === windowEnd.value) {
          found.push('window_same')
        } else if (!current.zones.includes(windowZone.value)) {
          found.push('window_zone')
        }
      }

      return found
    }

    if (form !== null && threads !== null && save !== null && windowAlways !== null && windowSet !== null &&
        windowFields !== null && windowStart !== null && windowEnd !== null && windowZone !== null) {
      save.hidden = false

      // Switching shows or hides the fields and saves nothing. The first
      // switch without a stored window starts with 22:00 to 06:00 in the zone
      // of the admin.
      const windowMode = function () {
        windowFields.hidden = !windowSet.checked
        if (windowSet.checked && typeof current.window.start !== 'string' &&
            windowStart.value === '' && windowEnd.value === '') {
          windowStart.value = '22:00'
          windowEnd.value = '06:00'
          if (current.zones.includes(current.defaultZone)) {
            windowZone.value = current.defaultZone
          }
        }
      }
      windowAlways.addEventListener('change', windowMode)
      windowSet.addEventListener('change', windowMode)

      form.addEventListener('submit', async function (event) {
        event.preventDefault()
        threadsWrong(false)
        windowWrong(null, [])
        const found = findings()
        if (found.length > 0) {
          // Nothing is sent; the focus goes to the first field that is wrong.
          const fields = found.map(wrong)
          if (fields[0] !== null) {
            fields[0].focus()
          }

          return
        }

        const count = Number(threads.value.trim())
        const payload = {
          // The default itself is sent as "no value of the admin".
          threads: count === current.threads.standard ? null : count,
          window: windowSet.checked
            ? { start: windowStart.value, end: windowEnd.value, zone: windowZone.value }
            : null
        }
        saving += 1
        save.disabled = true
        save.setAttribute('aria-busy', 'true')
        tell(computeStatus, '', false)
        let answer = null
        try {
          answer = await post('admin/resources', payload)
        } catch (error) {
          answer = null
        }
        saving -= 1
        save.disabled = false
        save.removeAttribute('aria-busy')
        if (answer !== null && answer.status === 200 && usable(answer.body)) {
          take(answer.body)
          tell(computeStatus, word(computeStatus, 'saved'), true)
          schedule()

          return
        }
        const field = answer !== null && answer.status === 400 && answer.body !== null &&
          typeof answer.body === 'object' ? wrong(answer.body.field) : null
        if (field !== null) {
          field.focus()
        } else {
          // The values stay in the form.
          tell(computeStatus, word(computeStatus, 'failed'), false)
        }
      })
    }

    // -- the offline switch: saved on every change ----------------------------------

    if (offline !== null) {
      offline.addEventListener('change', async function () {
        const wanted = offline.checked
        if (current.offline.forcedByEnv === true) {
          render(current)

          return
        }
        saving += 1
        offline.disabled = true
        tell(offlineStatus, '', false)
        let answer = null
        try {
          answer = await post('admin/resources', { offline: wanted })
        } catch (error) {
          answer = null
        }
        saving -= 1
        if (answer !== null && answer.status === 200 && usable(answer.body)) {
          take(answer.body)
          tell(offlineStatus, word(offlineStatus, 'saved'), true)
          schedule()

          return
        }
        tell(offlineStatus, word(offlineStatus, 'failed'), false)
        // The old value.
        render(current)
      })
    }

    // The states the server rendered are the start: nothing is announced for
    // them, and a download that is already running is followed from now on.
    for (const model of current.models) {
      if (model !== null && typeof model === 'object' && MODELS.includes(model.id)) {
        shownStates[model.id] = MODEL_STATES.includes(model.state) ? model.state : 'failed'
      }
    }
    schedule()
  }

  // -- the test result switch (debug mode only) --------------------------------

  const toggle = document.getElementById('avs-sample-visible')
  const status = document.getElementById('avs-sample-status')
  if (toggle === null || status === null) {
    return
  }

  let clearTimer = null

  toggle.addEventListener('change', async function () {
    const wanted = toggle.checked
    toggle.disabled = true
    window.clearTimeout(clearTimer)
    status.textContent = ''
    try {
      const answer = await send('admin/sample', { visible: wanted })
      if (answer === null || answer.visible !== wanted) {
        throw new Error('audio_video_search: switch not stored')
      }
      status.textContent = status.dataset.saved || ''
      clearTimer = window.setTimeout(function () {
        status.textContent = ''
      }, SAVED_FOR_MS)
    } catch (error) {
      toggle.checked = !wanted
      status.textContent = status.dataset.failed || ''
    } finally {
      toggle.disabled = false
    }
  })
})()
