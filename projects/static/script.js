const TIME_SLOTS = ['7AM-8AM', '8AM-9AM', '9AM-10AM', '10AM-11AM', '12PM-1PM', '2PM-3PM', '3PM-4PM', '4PM-5PM'];
let selectedRoom = null;
let currentDate = new Date();
let currentDayStart = 1;
let bookings = {};
let pendingBookings = new Set();
let userName = ''; // ⭐ NEW: Store current user name


document.addEventListener('DOMContentLoaded', function() {
    // ⭐ NEW: Get current user name from template
    userName = document.querySelector('.user-info .badge')?.textContent.replace('Room Booking for ', '') || '';
    
    loadBookings();
    
    document.querySelectorAll('.room-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            document.querySelectorAll('.room-btn').forEach(b => b.classList.remove('selected'));
            e.target.classList.add('selected');
            selectedRoom = e.target.dataset.room;
            document.getElementById('selected-room').innerHTML = `✅ Room ${selectedRoom} Selected`;
            document.getElementById('selected-room').classList.remove('d-none');
            document.getElementById('calendar-section').style.display = 'block';
            currentDayStart = 1;
            pendingBookings.clear();
            generateCalendar();
        });
    });

    setupNavigation();
    setupConfirmButton();
});


async function loadBookings() {
    try {
        const response = await fetch('/api/bookings');
        bookings = await response.json();
        console.log('Loaded bookings:', bookings);
        if (selectedRoom) generateCalendar();
    } catch (e) {
        console.log('No bookings yet');
        bookings = {};
    }
}


function generateCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const endDay = Math.min(currentDayStart + 6, daysInMonth);

    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    document.getElementById('month-year').textContent =
        currentDate.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    document.getElementById('day-range').textContent = `Days ${currentDayStart}-${endDay}`;

    let gridHTML = '<div class="date-header empty"></div>';

    // -------- DATE HEADERS --------
    for (let i = 0; i < 7; i++) {
        const day = currentDayStart + i;
        gridHTML += day <= daysInMonth
            ? `<div class="date-header">Day ${day}</div>`
            : `<div class="date-header empty"></div>`;
    }

    // -------- BODY --------
    TIME_SLOTS.forEach((time, row) => {
        gridHTML += `<div class="time-slot">${time}</div>`;

        for (let i = 0; i < 7; i++) {
            const day = currentDayStart + i;

            if (day > daysInMonth) {
                gridHTML += `<div class="booking-cell disabled"></div>`;
                continue;
            }

            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const cellId = `${selectedRoom}_${dateStr}_${row}`;
            const bookingData = bookings[cellId];

            if (dateStr < todayStr) {
                gridHTML += `<div class="booking-cell past">Past</div>`;
                continue;
            }

            // ⭐ MERGED BOOKING DETECTION (with owner check) ⭐
            if (bookingData) {
                const prevCellId = `${selectedRoom}_${dateStr}_${row - 1}`;
                const prevBooking = bookings[prevCellId];

                if (prevBooking && prevBooking.name === bookingData.name) {
                    continue;
                }

                let span = 1;
                let nextRow = row + 1;

                while (true) {
                    const nextCellId = `${selectedRoom}_${dateStr}_${nextRow}`;
                    const nextBooking = bookings[nextCellId];

                    if (nextBooking && nextBooking.name === bookingData.name) {
                        span++;
                        nextRow++;
                    } else {
                        break;
                    }
                }

                const isOwner = bookingData.name === userName;
                const startTime = TIME_SLOTS[row].split('-')[0];
                const endTime = TIME_SLOTS[row + span - 1].split('-')[1];

                gridHTML += `
                    <div class="booking-cell booked ${isOwner ? 'owner-booked' : ''} merged-booking"
                         style="grid-row: span ${span}" data-cell="${cellId}">
                        ${isOwner ? 'DR.' : 'Booked by'}
                        <strong>${bookingData.name}</strong>
                        ${isOwner ? '<br><small>Click to Remove</small>' : ''}
                    </div>
                `;
            } 
            // ---------- AVAILABLE ----------
            else {
                const cellClass = pendingBookings.has(cellId) ? 'pending' : '';
                const text = pendingBookings.has(cellId) ? 'Booking...' : 'Available';

                gridHTML += `
                    <div class="booking-cell ${cellClass}" data-cell="${cellId}">
                        ${text}
                    </div>
                `;
            }
        }
    });

    document.getElementById('calendar-grid').innerHTML = gridHTML;
    setupCellClicks();
    updatePagination(daysInMonth);
    updateConfirmButton();
}


function setupNavigation() {
    document.getElementById('prev-month').onclick = () => {
        currentDate.setMonth(currentDate.getMonth() - 1);
        currentDayStart = 1;
        generateCalendar();
    };
    
    document.getElementById('next-month').onclick = () => {
        currentDate.setMonth(currentDate.getMonth() + 1);
        currentDayStart = 1;
        generateCalendar();
    };
}


function setupCellClicks() {
    // Available cells - toggle booking
    document.querySelectorAll('.booking-cell:not(.booked):not(.disabled):not(.past)').forEach(cell => {
        cell.onclick = function(e) {
            const cellId = e.target.closest('.booking-cell').dataset.cell;
            if (pendingBookings.has(cellId)) {
                pendingBookings.delete(cellId);
            } else {
                pendingBookings.add(cellId);
            }
            generateCalendar();
            updateConfirmButton();
        };
    });

    // ⭐ NEW: Owner's own bookings - remove
    document.querySelectorAll('.booking-cell.owner-booked').forEach(cell => {
        cell.onclick = async function(e) {
            e.stopPropagation();
            const cellId = e.target.closest('.booking-cell').dataset.cell;
            
            if (confirm(`🗑️ Remove your booking?\nRoom ${selectedRoom}, ${cellId}`)) {
                cell.classList.add('pending'); // Visual feedback
                cell.textContent = 'Removing...';
                
                try {
                    const response = await fetch('/api/bookings', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cellId })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        cell.textContent = 'Removed ✅';
                        cell.classList.add('success-remove');
                        setTimeout(() => {
                            loadBookings();
                            generateCalendar();
                        }, 1000);
                    } else {
                        alert('❌ ' + result.message);
                        generateCalendar(); // Refresh
                    }
                } catch (error) {
                    alert('❌ Remove failed');
                    generateCalendar();
                }
            }
        };
    });
}


async function setupConfirmButton() {
    document.getElementById('confirm-booking').onclick = async function() {
        if (pendingBookings.size > 0) {
            this.disabled = true;
            document.getElementById('booking-status').innerHTML = 'Booking...';
            
            const promises = Array.from(pendingBookings).map(async cellId => {
                const response = await fetch('/api/bookings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cellId })
                });
                return response.json();
            });
            
            const results = await Promise.all(promises);
            const success = results.every(r => r.success);
            
            if (success) {
                document.getElementById('booking-status').innerHTML = 
                    `<div class="alert alert-success">✅ ${pendingBookings.size} slot(s) BOOKED successfully!</div>`;
                pendingBookings.clear();
                await loadBookings();
                generateCalendar();
                setTimeout(() => {
                    document.getElementById('confirm-section').style.display = 'none';
                }, 2000);
            } else {
                document.getElementById('booking-status').innerHTML = 
                    `<div class="alert alert-danger">❌ Some slots already booked!</div>`;
            }
            this.disabled = false;
        }
    };
}


function updateConfirmButton() {
    const btn = document.getElementById('confirm-booking');
    const status = document.getElementById('booking-status');
    const confirmSection = document.getElementById('confirm-section');
    
    if (pendingBookings.size === 0) {
        btn.disabled = true;
        btn.textContent = 'Confirm Booking';
        status.textContent = '';
        confirmSection.style.display = 'none';
    } else {
        btn.disabled = false;
        btn.textContent = `Confirm ${pendingBookings.size} Slot(s)`;
        status.innerHTML = `${pendingBookings.size} slot(s) selected`;
        confirmSection.style.display = 'block';
    }
}


function updatePagination(daysInMonth) {
    document.getElementById('prev-days').disabled = currentDayStart === 1;
    document.getElementById('prev-days').onclick = () => {
        currentDayStart = Math.max(1, currentDayStart - 7);
        generateCalendar();
    };
    
    const endDay = Math.min(currentDayStart + 6, daysInMonth);
    document.getElementById('next-days').disabled = endDay === daysInMonth;
    document.getElementById('next-days').onclick = () => {
        currentDayStart = Math.min(daysInMonth - 6, currentDayStart + 7);
        generateCalendar();
    };
}
